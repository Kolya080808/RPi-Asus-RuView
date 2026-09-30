"""Offline checks for the capture-to-PNG signal processing."""
import pathlib
import struct
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from capture_plot import series, session_id


def frame(timer, changed=False):
    raw=bytearray(320)
    struct.pack_into('<I',raw,16,0x04041004)
    struct.pack_into('<I',raw,20,timer & 0xffffffff)
    for i in range(56):
        struct.pack_into('<hh',raw,96+i*4,100+(i*10 if changed else 0),30)
    return {'raw_hex':raw.hex()}


class SignalTests(unittest.TestCase):
    def test_still_signal_and_three_intervals(self):
        for interval in [100000,200000,500000]:
            points,report=series([frame(i*interval) for i in range(25)])
            self.assertAlmostEqual(report['duration_s'],24*interval/1e6)
            self.assertEqual(report['gap_count'],0)
            self.assertTrue(all(p['step']==0 for p in points[1:]))

    def test_motion_and_elapsed_time_smoothing(self):
        points,_=series([frame(i*500000,i>=4) for i in range(9)])
        self.assertGreater(points[4]['step'],0)
        self.assertEqual(points[6]['smooth'],0)

    def test_invalid_and_gap_do_not_imply_stillness(self):
        points,report=series([frame(0),frame(100000),{'raw_hex':'bad'},frame(200000),frame(500000),frame(600000)])
        self.assertEqual(report['invalid_records'],1)
        self.assertIsNone(points[2]['step'])
        self.assertEqual(report['gap_count'],1)
        self.assertTrue(points[3]['gap_before'])
        self.assertIsNone(points[3]['smooth'])

    def test_timer_wrap_and_reset(self):
        points,_=series([frame(2**32-100000),frame(0),frame(100000)])
        self.assertAlmostEqual(points[-1]['seconds'],.2)
        with self.assertRaises(ValueError):series([frame(100000),frame(0)])

    def test_missing_data_and_session_validation(self):
        with self.assertRaises(ValueError):series([])
        with self.assertRaises(Exception):session_id('invalid; command')


if __name__=='__main__':
    unittest.main()
