"""Narrow reader rollback checks; all device operations mocked."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reader_probe as probe


class ReaderRollbackTests(unittest.TestCase):
    def setUp(self):
        self.before = {'boot_id': 'same', 'radios': {
            n: {'state': 'disabled counters=0', 'peers': ''} for n in ('eth1', 'eth2')}}
        self.plan = {'id': 'a' * 12, 'path': '/tmp/ruview-nl-' + 'a' * 12,
                     'sha256': probe.EXPECTED, 'target': 'ax58',
                     'action': 'socket-free-self-test', 'before_file': 'absent',
                     'before': self.before, 'status': 'self-test-passed'}
        self.client = Mock()
        for name, value in [('binary', b'exact reader'), ('processes', None),
                            ('baseline', copy.deepcopy(self.before))]:
            patcher = patch.object(probe, name, return_value=value)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def test_exact_file_removal_and_absence_verification(self):
        with patch.object(probe, 'remote_file', return_value=b'exact reader'), \
             patch.object(probe, 'command', side_effect=[
                 (b'present', b'', ''), (b'', b'', ''), (b'absent', b'', '')]) as command:
            probe.check(self.client, self.plan, apply=True)
        self.assertEqual(command.call_args_list[1].args[1], 'rm -f ' + self.plan['path'])

    def test_unknown_empty_partial_and_restored_files_never_removed(self):
        for data, status in [(b'', 'uploading'), (b'exact', 'uploading'),
                             (b'foreign', 'self-test-passed'), (b'exact reader', 'restored'),
                             (b'exact reader', 'prepared')]:
            with self.subTest(data=data, status=status):
                self.plan['status'] = status
                with patch.object(probe, 'remote_file', return_value=data), \
                     patch.object(probe, 'command', return_value=(b'present', b'', '')) as command:
                    with self.assertRaisesRegex(RuntimeError, 'not owned'):
                        probe.check(self.client, self.plan, apply=True)
                    self.assertEqual(command.call_count, 1)

    def test_boot_change_refuses_deletion(self):
        self.baseline.return_value['boot_id'] = 'changed'
        with patch.object(probe, 'remote_file', return_value=b'exact reader'), \
             patch.object(probe, 'command', return_value=(b'present', b'', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'boot identity'):
                probe.check(self.client, self.plan, apply=True)
            self.assertEqual(command.call_count, 1)

    def test_separately_inspected_partial_requires_exact_size_hash_and_prefix(self):
        self.plan['status'] = 'uploading'
        self.plan['inspected_partial'] = {'bytes': 5, 'sha256': hashlib.sha256(b'exact').hexdigest()}
        with patch.object(probe, 'remote_file', return_value=b'exact'), \
             patch.object(probe, 'command', side_effect=[
                 (b'present', b'', ''), (b'', b'', ''), (b'absent', b'', '')]) as command:
            probe.check(self.client, self.plan, apply=True)
        self.assertEqual(command.call_count, 3)
        self.plan['inspected_partial']['sha256'] = '0' * 64
        with patch.object(probe, 'remote_file', return_value=b'exact'), \
             patch.object(probe, 'command', return_value=(b'present', b'', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'not owned'):
                probe.check(self.client, self.plan, apply=True)
            self.assertEqual(command.call_count, 1)

    def test_process_present_prevents_file_access(self):
        self.processes.side_effect = RuntimeError('process present')
        with patch.object(probe, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'process present'):
                probe.check(self.client, self.plan, apply=True)
            command.assert_not_called()

    def test_changed_file_refuses_deletion(self):
        with patch.object(probe, 'remote_file', side_effect=[b'exact reader', b'changed']), \
             patch.object(probe, 'command', return_value=(b'present', b'', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'changed during rollback'):
                probe.check(self.client, self.plan, apply=True)
            self.assertEqual(command.call_count, 1)


if __name__ == '__main__':
    unittest.main()
