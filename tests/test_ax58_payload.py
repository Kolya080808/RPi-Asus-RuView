"""Synthetic structure and malformed-input checks; no private recordings."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import inspect_ax58_payload as audit
from raw_pipeline import MAGIC, encode_frame


def frame(tick=1, receive=1000, **kwargs):
    payload = bytearray(2048)
    struct.pack_into('<I', payload, 20, tick)
    packet = struct.pack('<IHHII', 2064, 0, 0, 0, 0) + payload
    return encode_frame(bytes(packet), source_monotonic_ns=receive, **kwargs)


class PayloadAuditTests(unittest.TestCase):
    def test_two_apart_reports_observed_ranges_and_suffix(self):
        base = bytes(2048)
        alternate = bytes([1]) * 2048
        changed = bytearray(base)
        changed[0] = changed[207] = 1
        report = audit.compare_two_apart([base, alternate, bytes(changed), alternate])
        self.assertEqual(report['differing_ranges_half_open'], [(0, 1), (207, 208)])
        self.assertEqual(report['identical_suffix_start'], 208)
        self.assertEqual(report['distinct_suffixes'], 2)
        self.assertIsNone(audit.compare_two_apart([base, alternate]))
        self.assertEqual(audit.compare_two_apart([base] * 3)['identical_suffix_start'], 0)
        self.assertEqual(audit.compare_two_apart([base, base, alternate])[
            'identical_suffix_start'], 2048)

    def test_modular_candidate_is_separate_from_receive_clock(self):
        result = audit.inspect(MAGIC + frame(0xfffffff0, 1000) + frame(0x10, 65000))
        self.assertEqual(result['intervals'][0]['candidate_ticks'], 32)
        self.assertEqual(result['intervals'][0]['receive_ms'], .064)
        self.assertEqual(result['distinct_payloads'], 2)
        self.assertNotIn('iq', result)

    def test_every_truncated_frame_boundary_rejected(self):
        data = MAGIC + frame()
        for length in range(len(MAGIC), len(data)):
            with self.subTest(length=length), self.assertRaises(ValueError):
                audit.inspect(data[:length])

    def test_receive_error_and_truncation_rejected(self):
        for flags in ({'truncated': True}, {'receive_error': 'ENOBUFS'}):
            with self.assertRaises(ValueError):
                audit.inspect(MAGIC + frame(**flags))

    def test_non_increasing_clock_rejected(self):
        with self.assertRaises(ValueError):
            audit.inspect(MAGIC + frame() + frame())

    def test_bad_datagram_length_rejected(self):
        packet = struct.pack('<I', 2048) + bytes(2060)
        with self.assertRaisesRegex(ValueError, 'Netlink length'):
            audit.inspect(MAGIC + encode_frame(packet, source_monotonic_ns=1))
