"""Offline audit input/candidate checks; no firmware or network required."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    import audit_ax58_network_export as ax58
    import audit_ax56_network_export as ax56
except ModuleNotFoundError:
    ax58 = ax56 = None


@unittest.skipIf(ax58 is None, 'requires optional firmware research dependencies')
class NetworkExportAuditTests(unittest.TestCase):
    def test_driver_markers_and_scsi_false_positive(self):
        self.assertEqual(ax58.marker_strings(b'scsi_send_eh_cmnd\0'), [])
        for value in (b'wlc_csimon_attach', b'CSI Monitor', b'csi_udp', b'netlink_csi'):
            self.assertTrue(ax58.marker_strings(value), value)

    def test_marker_beyond_long_line_prefix_is_retained(self):
        hits = ax58.marker_strings(b'x' * 5000 + b' csimon network ' + b'y' * 5000)
        self.assertEqual(len(hits), 1)
        self.assertIn('csimon', hits[0])
        self.assertLess(len(hits[0]), 600)

    def test_unexpected_inputs_refused_before_filesystem_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'wrong-image'
            source.write_bytes(b'not firmware')
            for module in (ax58, ax56):
                with self.subTest(module=module.__name__), self.assertRaises(ValueError):
                    module.audit(source)


if __name__ == '__main__':
    unittest.main()
