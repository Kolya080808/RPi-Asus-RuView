"""Provisional decoder for the observed GT-AX11000 eth6/20 MHz format.

This is a capture-specific hypothesis, not a general Broadcom CSI decoder.
The raw record must always be retained for re-decoding.
"""
import math
import re
import struct

PROFILE = 'gtax11000-eth6-ch4-20mhz-i16-candidate-v1'


def text_records(text):
    for part in text.split('CSI record:')[1:]:
        yield b''.join(struct.pack('<I', int(word, 16))
                       for word in re.findall(r'0x([0-9a-fA-F]{8})\b', part))


def decode(record):
    if len(record) < 320:
        raise ValueError('Incomplete record: need at least 320 bytes')
    if struct.unpack_from('<I', record, 16)[0] != 0x04041004:
        raise ValueError('Unrecognized channel/profile; retain raw data without decoding')
    values = struct.unpack_from('<112h', record, 96)
    pairs = list(zip(values[::2], values[1::2]))
    return {
        'profile': PROFILE,
        'interpretation': 'provisional; no validated pose or vital signs',
        'peer': record[4:10].hex(':'),
        'mac_b': record[10:16].hex(':'),
        'timer_candidate': struct.unpack_from('<I', record, 20)[0],
        'rssi_like': list(struct.unpack_from('4b', record, 28)),
        'iq': pairs,
        'amplitude': [math.hypot(i, q) for i, q in pairs],
    }
