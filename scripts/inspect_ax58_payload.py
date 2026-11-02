"""Offline structural audit of AX58 envelopes, not a CSI/IQ decoder.

Offsets in the report are relative to the 2048-byte payload after the retained
16-byte Netlink header. No device access, coefficient conversion or RF clock
assignment is performed. Reject incomplete/error-marked input explicitly.
"""
import argparse
import hashlib
import json
import logging
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from raw_pipeline import MAGIC, _load_json, _validate_header

LOG = logging.getLogger('ruview.ax58_payload')
MAX_BYTES = 6 * 1024**2


def inspect(data):
    if len(data) > MAX_BYTES or not data.startswith(MAGIC):
        raise ValueError('Expected bounded RUVRAW1 stream')
    offset = len(MAGIC)
    rows, payloads = [], []
    while offset < len(data):
        if len(data) - offset < 8:
            raise ValueError('Incomplete frame prefix')
        header_size, size = struct.unpack_from('<II', data, offset)
        offset += 8
        if not 0 < header_size <= 4096 or size != 2064:
            raise ValueError('Unexpected metadata/datagram length')
        if len(data) - offset < header_size + size:
            raise ValueError('Incomplete frame')
        metadata = _load_json(data[offset:offset + header_size])
        _validate_header(metadata)
        offset += header_size
        packet = data[offset:offset + size]
        offset += size
        if metadata['truncated'] or metadata['receive_error'] is not None:
            raise ValueError('Error-marked frame; retain raw input for inspection')
        stamp = metadata['source_monotonic_ns']
        if stamp is None or (rows and stamp <= rows[-1]['receive_ns']):
            raise ValueError('Missing or non-increasing receive clock')
        length, kind, flags, sequence, port = struct.unpack_from('<IHHII', packet)
        if length != size:
            raise ValueError('Netlink length mismatch')
        payload = packet[16:]
        payloads.append(payload)
        rows.append(dict(reader_sequence=metadata['source_sequence'], receive_ns=stamp,
                         netlink_opaque=dict(type=kind, flags=flags, sequence=sequence, port=port),
                         address_at_4=payload[4:10].hex(':'),
                         address_at_10=payload[10:16].hex(':'),
                         word_at_16=hex(struct.unpack_from('<I', payload, 16)[0]),
                         timer_candidate_at_20=struct.unpack_from('<I', payload, 20)[0],
                         word_at_24=hex(struct.unpack_from('<I', payload, 24)[0]),
                         signed_bytes_at_28=list(struct.unpack_from('4b', payload, 28)),
                         payload_sha256=hashlib.sha256(payload).hexdigest()))
    if not rows:
        raise ValueError('No frames')
    intervals = []
    for previous, current in zip(rows, rows[1:]):
        receive_ms = (current['receive_ns'] - previous['receive_ns']) / 1e6
        ticks = (current['timer_candidate_at_20'] - previous['timer_candidate_at_20']) % 2**32
        intervals.append(dict(receive_ms=receive_ms, candidate_ticks=ticks,
                              residual_ms_if_microseconds=ticks / 1000 - receive_ms))
    return dict(schema='ax58-structure-v1', stream_sha256=hashlib.sha256(data).hexdigest(),
                stream_bytes=len(data), frames=rows, intervals=intervals,
                varying_byte_offsets=[i for i in range(2048)
                                      if len({p[i] for p in payloads}) > 1],
                distinct_payloads=len({r['payload_sha256'] for r in rows}),
                limits='Structural observations only; timer units, IQ layout, loss and motion unvalidated')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        with args.input.open('rb') as stream:
            result = inspect(stream.read(MAX_BYTES + 1))
        # Never overwrite existing evidence or an output from another analysis.
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        LOG.info('Structural audit frames=%d output=%s', len(result['frames']), args.output)
    except Exception:
        LOG.exception('Offline AX58 audit failed; source data unchanged')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
