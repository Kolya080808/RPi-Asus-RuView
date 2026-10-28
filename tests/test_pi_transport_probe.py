"""Pi probe payload and rollback guards exercised on the PC only."""
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import pi_transport_probe as probe


class PiTransportProbeTests(unittest.TestCase):
    def plan(self):
        return dict(id='012345abcdef', path='/tmp/ruview-transport-012345abcdef',
                    before_path='absent', status='prepared', before={'boot': 'test', 'panel': 'active'})

    def test_exact_payload_runs_locally_and_has_only_three_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'probe'
            code = probe.payload(str(output))
            self.assertLess(len(code), 65536)
            result = subprocess.run([sys.executable, '-B', '-', 'synthetic-local'],
                                    input=code, capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(set(p.name for p in output.iterdir()), probe.FILES)
            self.assertEqual(report['result']['status'], 'received')
            self.assertEqual(report['integrity'], 'ok')
            for name, expected in report['files'].items():
                self.assertEqual(probe.digest((output / name).read_bytes()), expected)

    def test_plan_cannot_escape_fixed_scope(self):
        plan = self.plan()
        probe.validate(plan)
        for path in ('/home/pi/ruview-lab', '/tmp/ruview-transport-012345abcdef/..'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                probe.validate(dict(plan, path=path))

    def test_inspection_refuses_symlink_unknown_files_or_unmeasured_run(self):
        plan = self.plan()
        sftp = Mock()
        with patch.object(probe, 'baseline', return_value=plan['before']), \
             patch.object(probe.deployment, 'run', return_value=''):
            sftp.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFLNK)
            with self.assertRaises(RuntimeError):
                probe.inspect(None, sftp, dict(plan, status='running'))
            sftp.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFDIR)
            with self.assertRaisesRegex(RuntimeError, 'inventory'):
                probe.inspect(None, sftp, dict(plan, status='running'))
            sftp.listdir.return_value = ['unknown']
            with self.assertRaisesRegex(RuntimeError, 'Unknown files'):
                probe.inspect(None, sftp, dict(plan, status='measured',
                                              files=dict.fromkeys(probe.FILES, '0'*64)))
            sftp.remove.assert_not_called()

    def test_inspection_refuses_active_process_and_changed_baseline(self):
        plan = self.plan()
        with patch.object(probe, 'baseline', return_value={'boot': 'changed'}):
            with self.assertRaisesRegex(RuntimeError, 'state changed'):
                probe.inspect(None, Mock(), plan)
        with patch.object(probe, 'baseline', return_value=plan['before']), \
             patch.object(probe.deployment, 'run', return_value='python3 -B - ruview-transport-' + plan['id']):
            with self.assertRaisesRegex(RuntimeError, 'process still present'):
                probe.inspect(None, Mock(), plan)

    def test_apply_requires_local_evidence_before_any_deletion(self):
        plan = dict(self.plan(), status='measured')
        client = Mock()
        sftp = client.open_sftp.return_value.__enter__ = Mock(return_value=Mock())
        client.open_sftp.return_value.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(probe, 'ROOT', Path(folder)), \
             patch.object(probe.deployment, 'load_manifest', return_value={'pi_transport_checks': [plan]}), \
             patch.object(probe.deployment, 'connect', return_value=client), \
             patch.object(probe, 'inspect', return_value={'raw.sqlite3': b'keep'}):
            with self.assertRaisesRegex(RuntimeError, 'evidence missing'):
                probe.rollback(True)
            sftp.return_value.remove.assert_not_called()

    def test_apply_removes_only_verified_files_then_checks_absence(self):
        plan = dict(self.plan(), status='measured')
        contents = dict.fromkeys(probe.FILES, b'synthetic')
        client = Mock()
        sftp = Mock()
        client.open_sftp.return_value.__enter__ = Mock(return_value=sftp)
        client.open_sftp.return_value.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(probe, 'ROOT', Path(folder)), \
             patch.object(probe.deployment, 'load_manifest', return_value={'pi_transport_checks': [plan]}), \
             patch.object(probe.deployment, 'save_manifest'), \
             patch.object(probe.deployment, 'connect', return_value=client), \
             patch.object(probe, 'inspect', side_effect=[contents, contents, {}]) as inspect:
            evidence = Path(folder) / 'recordings' / ('pi-transport-' + plan['id'])
            evidence.mkdir(parents=True)
            for name, data in contents.items():
                (evidence / name).write_bytes(data)
            probe.rollback(True)
            self.assertEqual({call.args[0] for call in sftp.remove.call_args_list},
                             {plan['path'] + '/' + name for name in probe.FILES})
            sftp.rmdir.assert_called_once_with(plan['path'])
            self.assertEqual(inspect.call_args.args[2]['status'], 'restored')
            self.assertEqual(plan['status'], 'restored')


if __name__ == '__main__':
    unittest.main()
