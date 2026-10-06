"""Narrow capture recovery refuses unknown or subsequently changed device state."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import rollback
import deploy_panel


class CaptureRollbackTests(unittest.TestCase):
    def check(self, enabled='0', peers='', collectors='', apply=False, status='prepared'):
        plan = {'router': '192.168.50.1', 'interface': 'eth6', 'peer': 'A0:36:BC:16:85:B9',
                'initial_enabled': 0, 'initial_peers': [], 'initial_collectors': [],
                'sessions': ['fixture'], 'status': status}
        replies = iter(['CSI Monitor: Enabled: ' + enabled, peers, collectors,
                        '', 'CSI Monitor: Enabled: 0', ''])
        with patch.object(rollback, 'manifest', return_value={'panel_capture_verification': plan}), \
             patch.object(deploy_panel, 'connect', return_value=Mock()), \
             patch.object(deploy_panel, 'save_manifest') as save, \
             patch.object(deploy_panel, 'health', return_value={'active_capture': None}), \
             patch.object(rollback, 'run', side_effect=lambda *args: next(replies)) as run:
            rollback.capture_only(apply)
            if apply and status == 'recovery_required':
                self.assertEqual(plan['status'], 'restored')
                save.assert_called_once()
            else:
                save.assert_not_called()
            return run.call_count

    def test_idle_check_only_reads(self):
        self.assertEqual(self.check(), 3)

    def test_unknown_peer_or_process_is_never_stopped(self):
        for args in ({'peers': 'AA:BB:CC:DD:EE:FF'}, {'collectors': '123'}):
            with self.assertRaisesRegex(RuntimeError, 'Unknown monitor'):
                self.check(apply=True, status='recovery_required', **args)

    def test_prepared_or_verified_plan_cannot_disable_later_monitor(self):
        for status in ('prepared', 'verified'):
            with self.assertRaisesRegex(RuntimeError, 'not restored'):
                self.check(enabled='1', apply=True, status=status)

    def test_explicit_recovery_restores_only_owned_idle_monitor(self):
        self.assertEqual(self.check(enabled='1', peers='A0:36:BC:16:85:B9',
                                    apply=True, status='recovery_required'), 6)


if __name__ == '__main__':
    unittest.main()
