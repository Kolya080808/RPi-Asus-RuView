"""Active-plan validation on PC; never invokes a device command."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import active_reader_probe as active


class ActivePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        build = Path(self.temp.name)
        for name in ('reader', 'supervisor'):
            (build / name).write_bytes(name.encode())
        self.patch = patch.object(active, 'BUILD', build)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.plan = dict(id='012345abcdef', target='ax58', interface='wl0.1',
                         peer=active.PEER, protocol=23, seconds=5, interval_ms=500,
                         status='prepared', before={'boot_id':'boot'},
                         files={name:dict(path='/tmp/ruview-active-012345abcdef-'+name,
                             sha256=active.sha(name.encode()), before='absent')
                             for name in ('reader','supervisor')})

    def test_bounds_target_peer_and_path_are_fixed(self):
        active.validate(self.plan)
        for key, value in [('target','ax56'),('interface','eth2'),('peer','00:00:00:00:00:00'),
                           ('seconds',60),('protocol',22),('interval_ms',10)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                active.validate(dict(self.plan, **{key:value}))
        plan = copy.deepcopy(self.plan)
        plan['files']['reader']['path']='/tmp/unowned'
        with self.assertRaises(ValueError):active.validate(plan)

    def test_reboot_prevents_file_deletion(self):
        with patch.object(active.reader, 'baseline', return_value={'boot_id':'new'}), \
             patch.object(active, 'cmd') as cmd:
            with self.assertRaisesRegex(RuntimeError,'rebooted'):
                active.check(None,self.plan,True)
            cmd.assert_not_called()

    def test_partial_file_is_never_removed(self):
        with patch.object(active.reader,'baseline',return_value={'boot_id':'boot'}), \
             patch.object(active.reader,'processes'), \
             patch.object(active,'cmd',return_value='present') as cmd, \
             patch.object(active.reader,'remote_file',return_value=b'partial'):
            with self.assertRaisesRegex(RuntimeError,'partial'):
                active.check(None,dict(self.plan,status='uploading'),True)
            self.assertFalse(any('rm -f' in c.args[1] for c in cmd.call_args_list))

    def test_run_refuses_without_acceptance_and_does_not_connect(self):
        with patch.object(active.reader,'connect') as connect:
            with self.assertRaises(RuntimeError):active.run(False)
            connect.assert_not_called()

    def test_roamed_away_pi_stops_readiness_without_mutation(self):
        with patch.object(active, 'cmd', side_effect=['1', 'up', 'Enabled: 0', '', '']) as command:
            with self.assertRaisesRegex(RuntimeError, 'identified Pi'):
                active.ready(None)
            self.assertEqual(command.call_count, 5)
            self.assertTrue(all(' enable' not in c.args[1] and ' add ' not in c.args[1]
                                for c in command.call_args_list))


if __name__ == '__main__':unittest.main()
