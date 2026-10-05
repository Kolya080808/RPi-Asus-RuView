"""Safety boundaries for the narrow repeater rollback; no device connections."""
import sys
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import repeater_probe as probe


class RepeaterRollbackTests(unittest.TestCase):
    def test_capture_disabled_before_any_connection(self):
        with patch.object(probe, 'connect') as connect:
            with self.assertRaisesRegex(RuntimeError, 'capture disabled'):
                probe.capture()
            connect.assert_not_called()

    def test_unresolved_incident_cannot_be_hidden_by_new_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {'repeater_probes': [{'status': 'restored', 'incident': {'resolved': False}}]}
            path = root / 'deployment.json'
            path.write_text(json.dumps(manifest))
            before = path.read_bytes()
            with patch.object(probe, 'ROOT', root), patch.object(probe, 'connect') as connect:
                with self.assertRaisesRegex(RuntimeError, 'Unresolved repeater incident'):
                    probe.prepare('ax58', 'eth1')
                connect.assert_not_called()
                self.assertEqual(path.read_bytes(), before)

    def setUp(self):
        self.plan = {'interface': 'eth1', 'peer': 'AA:BB:CC:DD:EE:FF',
                     'path': '/tmp/ruview-csimond-012345abcdef', 'sha256': probe.digest(b'expected')}
        self.state = {'state': 'CSI Monitor: Enabled: 0', 'peers': '',
                      'processes': '', 'netlink': 'header\n', 'associated': ''}

    def check(self, state=None, data=b'expected', apply=False):
        with patch.object(probe, 'validate'), patch.object(probe, 'inspect', return_value=state or self.state), \
             patch.object(probe, 'remote_file', return_value=data), patch.object(probe, 'run') as run:
            try:
                return probe.check(None, self.plan, apply)
            finally:
                run.assert_not_called()

    def test_check_does_not_write(self):
        self.check()

    def test_changed_file_rejected_before_mutation(self):
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            self.check(data=b'unknown', apply=True)

    def test_foreign_peer_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'peer configuration'):
            self.check({**self.state, 'peers': 'AA:BB:CC:DD:EE:00'}, apply=True)

    def test_unowned_enabled_monitor_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'monitor state'):
            self.check({**self.state, 'state': 'CSI Monitor: Enabled: 1'}, apply=True)

    def test_running_collector_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'still running'):
            self.check({**self.state, 'processes': '123 /tmp/ruview-csimond-other'}, apply=True)

    def test_restored_operation_cannot_disable_later_monitor(self):
        self.plan['status'] = 'restored'
        with self.assertRaisesRegex(RuntimeError, 'must be disabled'):
            self.check({**self.state, 'state': 'CSI Monitor: Enabled: 1',
                        'peers': self.plan['peer']}, apply=True)

    def test_existing_netlink_listener_blocks_probe(self):
        with self.assertRaisesRegex(RuntimeError, 'listener'):
            probe.idle({**self.state, 'netlink': 'header\n0000 23 99 0 0\n'})


if __name__ == '__main__':
    unittest.main()
