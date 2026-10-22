"""Passive-reader planning and cleanup with device access mocked."""
import copy
from contextlib import ExitStack
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import passive_reader_probe as probe


class PassiveReaderTests(unittest.TestCase):
    def setUp(self):
        self.before = {'boot_id': 'same', 'radios': {
            interface: {'state': 'disabled counters=0', 'peers': ''}
            for interface in ('eth1', 'eth2')}}
        self.plan = {'id': 'b' * 12, 'path': '/tmp/ruview-passive-' + 'b' * 12,
                     'target': 'ax58', 'action': probe.ACTION,
                     'sha256': probe.reader.EXPECTED, 'before_file': 'absent',
                     'protocol': 23, 'seconds': 2, 'status': 'uploaded',
                     'before': self.before}
        self.client = Mock()
        for name, value in [('binary', b'exact reader'), ('processes', None),
                            ('baseline', copy.deepcopy(self.before))]:
            patcher = patch.object(probe.reader, name, return_value=value)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def test_no_data_is_expected_only_with_complete_matching_evidence(self):
        expected = b'bounded reader exit=3 records=0; driver loss unknown\n'
        self.assertEqual(probe.outcome(b'RUVRAW1\n', expected, 3), 'expected-no-data')
        for stdout, stderr, status in [
                (b'', expected, 3), (b'RUVRAW1\npartial', expected, 3),
                (b'RUVRAW1\n', b'', 3), (b'RUVRAW1\n', expected, 0),
                (b'RUVRAW1\n', expected, 2), (b'RUVRAW1\n', expected, 4),
                (b'RUVRAW1\n', expected, 124), (b'RUVRAW1\n', expected, 130),
                (b'RUVRAW1\n', expected, None)]:
            with self.subTest(status=status, stdout=stdout):
                with self.assertRaises(RuntimeError):
                    probe.outcome(stdout, stderr, status)

    def test_self_test_plan_and_changed_bounds_rejected(self):
        for field, value in [('action', 'socket-free-self-test'), ('seconds', 8),
                             ('protocol', 24), ('protocol', True),
                             ('path', '/tmp/ruview-nl-' + 'b' * 12),
                             ('status', 'unknown'), ('target', 'ax56')]:
            with self.subTest(field=field):
                with self.assertRaises(RuntimeError):
                    probe.validate(dict(self.plan, **{field: value}))

    def test_exact_owned_file_removed_and_baseline_rechecked(self):
        with patch.object(probe.reader, 'remote_file', side_effect=[b'exact reader', b'exact reader', b'']), \
             patch.object(probe.reader, 'command', side_effect=[
                 (b'present', b'', ''), (b'', b'', ''), (b'absent', b'', '')]) as command:
            probe.check(self.client, self.plan, apply=True)
        self.assertEqual(command.call_args_list[1].args[1], 'rm -f ' + self.plan['path'])
        self.assertEqual(self.baseline.call_count, 2)

    def test_unknown_partial_and_unowned_files_retained(self):
        for data, status in [(b'', 'uploading'), (b'exact', 'uploading'),
                             (b'foreign', 'uploaded'), (b'exact reader', 'restored'),
                             (b'exact reader', 'prepared-blocked')]:
            with self.subTest(status=status, data=data), \
                 patch.object(probe.reader, 'remote_file', return_value=data), \
                 patch.object(probe.reader, 'command', return_value=(b'present', b'', '')) as command:
                with self.assertRaises(RuntimeError):
                    probe.check(self.client, dict(self.plan, status=status), apply=True)
                self.assertEqual(command.call_count, 1)

    def test_changed_boot_or_monitor_blocks_cleanup(self):
        for field in ('boot', 'state', 'peers'):
            changed = copy.deepcopy(self.before)
            if field == 'boot':
                changed['boot_id'] = 'different'
            else:
                changed['radios']['eth1'][field] = 'different'
            self.baseline.return_value = changed
            with self.subTest(field=field), \
                 patch.object(probe.reader, 'remote_file', return_value=b'exact reader'), \
                 patch.object(probe.reader, 'command', return_value=(b'present', b'', '')) as command:
                with self.assertRaises(RuntimeError):
                    probe.check(self.client, self.plan, apply=True)
                self.assertEqual(command.call_count, 1)

    def test_live_process_blocks_file_access(self):
        self.processes.side_effect = RuntimeError('process present')
        with patch.object(probe.reader, 'command') as command:
            with self.assertRaises(RuntimeError):
                probe.check(self.client, self.plan, apply=True)
            command.assert_not_called()

    def test_changed_file_refuses_removal(self):
        with patch.object(probe.reader, 'remote_file', side_effect=[b'exact reader', b'changed']), \
             patch.object(probe.reader, 'command', return_value=(b'present', b'', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'changed during'):
                probe.check(self.client, self.plan, apply=True)
            self.assertEqual(command.call_count, 1)

    def test_file_appearing_during_inspection_is_not_accepted(self):
        with patch.object(probe.reader, 'remote_file', return_value=b'exact reader'), \
             patch.object(probe.reader, 'command', return_value=(b'absent', b'', '')) as command:
            with self.assertRaisesRegex(RuntimeError, 'appeared during'):
                probe.check(self.client, self.plan)
            self.assertEqual(command.call_count, 1)

    def test_prepare_preserves_existing_manifest_and_never_uploads(self):
        manifest = {'existing': {'keep': True}, 'reader_self_tests': [{'status': 'restored'}]}
        with patch.object(probe.reader, 'load', return_value=manifest), \
             patch.object(probe.reader, 'connect', return_value=self.client), \
             patch.object(probe.reader, 'save_manifest') as save, \
             patch.object(probe, 'check') as check:
            plan = probe.prepare(23)
        self.assertEqual(plan['initial_execution_gate'], 'blocked-pending-review-or-explicit-risk-acceptance')
        self.assertEqual(plan['status'], 'prepared-blocked')
        self.assertEqual(manifest['existing'], {'keep': True})
        self.assertEqual(manifest['passive_reader_checks'], [plan])
        check.assert_called_once_with(self.client, plan)
        save.assert_called_once_with(manifest)
        self.client.close.assert_called_once()

    def test_pending_plan_refuses_new_connection(self):
        with patch.object(probe.reader, 'load', return_value={'passive_reader_checks': [self.plan]}), \
             patch.object(probe.reader, 'connect') as connect:
            with self.assertRaises(RuntimeError):
                probe.prepare(23)
            connect.assert_not_called()

    def run_mocks(self, stack, status=3, stdout=b'RUVRAW1\n', stderr=None):
        self.plan.update(status='prepared-blocked', rollback_checked_utc='checked')
        manifest = {'passive_reader_checks': [self.plan]}
        stack.enter_context(patch.object(probe.reader, 'load', return_value=manifest))
        stack.enter_context(patch.object(probe.reader, 'connect', return_value=self.client))
        stack.enter_context(patch.object(probe.reader, 'save_manifest'))
        stack.enter_context(patch.object(probe.reader, 'remote_file', return_value=b'exact reader'))
        command = stack.enter_context(patch.object(probe.reader, 'command', return_value=(b'', b'', '')))
        check = stack.enter_context(patch.object(probe, 'check', return_value=self.before))
        evidence = probe.reader.ROOT / 'recordings/passive-reader' / self.plan['id'] / 'fixture'
        collect = stack.enter_context(patch.object(probe.reader, 'collect', return_value=(
            stdout, stderr if stderr is not None else
            b'bounded reader exit=3 records=0; driver loss unknown\n', status, evidence)))
        return command, check, collect

    def test_run_requires_acceptance_before_loading_or_connecting(self):
        with patch.object(probe.reader, 'load') as load:
            with self.assertRaisesRegex(RuntimeError, 'acceptance'):
                probe.run(self.plan['id'])
            load.assert_not_called()

    def test_run_no_data_has_exact_command_and_verified_cleanup(self):
        with ExitStack() as stack:
            command, check, collect = self.run_mocks(stack)
            probe.run(self.plan['id'], True)
            self.assertEqual(collect.call_args.args[1], f'exec {self.plan["path"]} 23 2')
            self.assertEqual(command.call_count, 2)
            self.assertEqual(check.call_count, 4)
            self.assertTrue(check.call_args_list[2].kwargs['apply'])
        self.assertEqual(self.plan['status'], 'restored')
        self.assertEqual(self.plan['outcome'], 'expected-no-data')
        self.assertIn('cleanup_verified_utc', self.plan)

    def test_unexpected_receive_keeps_evidence_and_cleans_up_without_retry(self):
        with ExitStack() as stack:
            _, check, collect = self.run_mocks(stack, status=2, stderr=b'netlink bind failed\n')
            with self.assertRaisesRegex(RuntimeError, 'unexpected'):
                probe.run(self.plan['id'], True)
            collect.assert_called_once()
            self.assertEqual(check.call_count, 4)
        self.assertEqual(self.plan['status'], 'restored')
        self.assertEqual(self.plan['outcome'], 'unexpected-result')
        self.assertEqual(self.plan['receive']['exit_status'], 2)

    def test_transport_failure_preserves_running_state_and_does_not_claim_cleanup(self):
        with ExitStack() as stack:
            _, check, collect = self.run_mocks(stack)
            collect.side_effect = RuntimeError('transport interrupted')
            with self.assertRaisesRegex(RuntimeError, 'transport interrupted'):
                probe.run(self.plan['id'], True)
            self.assertEqual(check.call_count, 2)
        self.assertEqual(self.plan['status'], 'running')
        self.assertIn('receive_evidence_root', self.plan)
        self.assertNotIn('cleanup_verified_utc', self.plan)

    def test_changed_baseline_refuses_upload(self):
        with ExitStack() as stack:
            command, check, collect = self.run_mocks(stack)
            check.side_effect = RuntimeError('baseline changed')
            with self.assertRaisesRegex(RuntimeError, 'baseline changed'):
                probe.run(self.plan['id'], True)
            command.assert_not_called()
            collect.assert_not_called()

    def test_upload_mismatch_prevents_receive_and_preserves_ownership_state(self):
        with ExitStack() as stack:
            command, _, collect = self.run_mocks(stack)
            stack.enter_context(patch.object(probe.reader, 'remote_file', return_value=b'partial'))
            with self.assertRaisesRegex(RuntimeError, 'upload verification'):
                probe.run(self.plan['id'], True)
            collect.assert_not_called()
            self.assertEqual(command.call_count, 1)
        self.assertEqual(self.plan['status'], 'uploading')

    def test_run_rejects_wrong_plan_reuse_and_missing_dry_check_before_connecting(self):
        for identifier, status, dry_checked in [
                ('c' * 12, 'prepared-blocked', True),
                (self.plan['id'], 'restored', True),
                (self.plan['id'], 'prepared-blocked', False)]:
            plan = dict(self.plan, status=status)
            if dry_checked:
                plan['rollback_checked_utc'] = 'checked'
            with self.subTest(identifier=identifier, status=status, dry_checked=dry_checked), \
                 patch.object(probe.reader, 'load', return_value={'passive_reader_checks': [plan]}), \
                 patch.object(probe.reader, 'connect') as connect:
                with self.assertRaises(RuntimeError):
                    probe.run(identifier, True)
                connect.assert_not_called()

    def test_final_cleanup_failure_never_marks_restored(self):
        with ExitStack() as stack:
            _, check, _ = self.run_mocks(stack)
            check.side_effect = [self.before, self.before, self.before,
                                 RuntimeError('final baseline changed')]
            with self.assertRaisesRegex(RuntimeError, 'final baseline changed'):
                probe.run(self.plan['id'], True)
        self.assertEqual(self.plan['status'], 'finished')
        self.assertNotIn('cleanup_verified_utc', self.plan)


if __name__ == '__main__':
    unittest.main()
