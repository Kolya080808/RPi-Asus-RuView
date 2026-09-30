import pathlib
import struct
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from decoder import text_records
from live_signal import LiveParser,LiveSignal


def raw(timer,changed=False):
    data=bytearray(320)
    struct.pack_into('<II',data,16,0x04041004,timer & 0xffffffff)
    for i in range(56):struct.pack_into('<hh',data,96+i*4,100+i*(10 if changed else 0),30)
    return bytes(data)


class LiveTests(unittest.TestCase):
    def test_fragmented_real_stream(self):
        text=(ROOT/'evidence/asus-csi-probe.txt').read_text()
        expected=[r[:320] for r in text_records(text) if len(r)>=320]
        for size in (1,7,4096):
            parser=LiveParser();found=[]
            for pos in range(0,len(text),size):found.extend(parser.feed(text[pos:pos+size]))
            self.assertEqual(found,expected)

    def test_emit_before_next_record_or_tail(self):
        record=raw(0)
        text='CSI record:\n'+' '.join(f'0x{w:08x}' for w in struct.unpack('<80I',record))+'\n'
        parser=LiveParser()
        self.assertEqual(parser.feed(text),[record])
        self.assertEqual(parser.feed(' 0x11111111\n'),[])

    def test_smoothing_motion_gaps_and_wrap(self):
        s=LiveSignal(smoothing=1)
        s.add(raw(2**32-100000))
        self.assertEqual(s.add(raw(0))['step'],0)
        p=s.add(raw(100000,True))
        self.assertGreater(p['smooth'],0)
        self.assertLess(p['smooth'],p['step'])
        self.assertTrue(s.add(raw(600000))['gap'])
        self.assertIsNone(s.smooth)

    def test_bad_profile_resets_filter(self):
        s=LiveSignal();s.add(raw(0))
        with self.assertRaises(ValueError):s.add(b'bad')
        self.assertIsNone(s.add(raw(100000))['step'])


if __name__=='__main__':unittest.main()
