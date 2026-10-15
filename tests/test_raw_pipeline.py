"""Offline synthetic fixtures and real SQLite failures; no device access."""
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import raw_pipeline as pipeline


def descriptor(kind='csimond-payload', profile=pipeline.decoder.PROFILE):
    value = dict.fromkeys(pipeline.SOURCE_FIELDS)
    value.update(source_id='synthetic-link', operation_id='offline-test',
                 configuration={}, kind=kind, profile=profile, origin='synthetic')
    return value


def payload(size=2048):
    raw = bytearray(size)
    struct.pack_into('<I', raw, 16, 0x04041004)
    struct.pack_into('<112h', raw, 96, *range(112))
    return bytes(raw)


class Fragments:
    def __init__(self, chunks, error=None):
        self.chunks = iter(chunks)
        self.error = error

    def read(self, size):
        try:
            return next(self.chunks)
        except StopIteration:
            if self.error:
                raise self.error
            return b''


class RawPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / 'raw.sqlite3'
        self.derived = self.root / 'derived.sqlite3'
        self.wire = pipeline.MAGIC + pipeline.encode_frame(payload())

    def query(self, path, sql):
        with closing(sqlite3.connect(path)) as connection:
            return connection.execute(sql).fetchall()

    def original_bytes(self):
        return b''.join(row[0] for row in self.query(self.raw, 'SELECT raw FROM chunks ORDER BY seq'))

    def ingest(self, wire=None, source=None):
        return pipeline.ingest(io.BytesIO(self.wire if wire is None else wire), self.raw,
                               descriptor() if source is None else source)

    def test_fragmented_stream_and_delayed_decode_preserve_every_byte(self):
        wire = self.wire + pipeline.encode_frame(payload(), source_sequence=20, source_monotonic_ns=90)
        fragments = [wire[i:i+7] for i in range(0, len(wire), 7)]
        with patch.object(pipeline.decoder, 'decode', side_effect=AssertionError('Acquisition decoded input')):
            pipeline.ingest(Fragments(fragments), self.raw, descriptor())
        before = hashlib.sha256(self.raw.read_bytes()).hexdigest()
        result = pipeline.process(self.raw, self.derived)
        self.assertEqual(result, dict(status='processed', frames=2, invalid_frames=0))
        self.assertEqual(self.original_bytes(), wire)
        self.assertEqual(before, hashlib.sha256(self.raw.read_bytes()).hexdigest())
        frames = self.query(self.derived, 'SELECT payload_offset,payload_bytes,metadata,status FROM frames')
        for offset, length, _, status in frames:
            self.assertEqual(wire[offset:offset+length], payload())
            self.assertEqual(status, 'decoded')
        self.assertEqual(json.loads(frames[1][2])['source_sequence'], 20)

    def test_partial_final_payload_retained_and_previous_result_survives(self):
        wire = self.wire + pipeline.encode_frame(payload())[:-17]
        self.ingest(wire)
        with self.assertRaisesRegex(ValueError, 'Incomplete envelope'):
            pipeline.process(self.raw, self.derived)
        self.assertEqual(self.original_bytes(), wire)
        self.assertEqual(self.query(self.derived, 'SELECT status FROM processing'), [('failed',)])
        self.assertEqual(self.query(self.derived, 'SELECT count(*) FROM frames'), [(1,)])

    def test_interrupted_transport_keeps_complete_and_incomplete_input(self):
        wire = self.wire + b'\x01\x02'
        with self.assertRaises(ConnectionError):
            pipeline.ingest(Fragments([self.wire, b'\x01\x02'], ConnectionError('synthetic disconnect')),
                            self.raw, descriptor())
        self.assertEqual(self.original_bytes(), wire)
        self.assertEqual(self.query(self.raw, 'SELECT status FROM acquisition'), [('failed',)])
        with self.assertRaisesRegex(ValueError, 'Incomplete envelope'):
            pipeline.process(self.raw, self.derived)

    def test_transport_failure_with_whole_frames_never_reports_complete(self):
        with self.assertRaises(ConnectionError):
            pipeline.ingest(Fragments([self.wire], ConnectionError('synthetic disconnect')),
                            self.raw, descriptor())
        self.assertEqual(pipeline.process(self.raw, self.derived)['status'], 'partial')

    def test_unknown_netlink_profile_is_opaque_even_with_gt_profile_label(self):
        datagram = bytes(range(16)) + payload()
        self.ingest(pipeline.MAGIC + pipeline.encode_frame(datagram), descriptor('netlink-datagram'))
        with patch.object(pipeline.decoder, 'decode', side_effect=AssertionError('Unexpected decode')):
            self.assertEqual(pipeline.process(self.raw, self.derived)['status'], 'processed')
        self.assertEqual(self.query(self.derived, 'SELECT status FROM frames'), [('raw-only',)])
        self.assertIn(datagram, self.original_bytes())

    def test_unknown_payload_profile_remains_raw_only(self):
        self.ingest(source=descriptor(profile='unknown'))
        pipeline.process(self.raw, self.derived)
        self.assertEqual(self.query(self.derived, 'SELECT status FROM frames'), [('raw-only',)])

    def test_prefix_is_not_promoted_to_full_record(self):
        self.ingest(pipeline.MAGIC + pipeline.encode_frame(payload(320)), descriptor('legacy-prefix'))
        pipeline.process(self.raw, self.derived)
        self.assertEqual(self.query(self.derived, 'SELECT payload_bytes,status FROM frames'), [(320, 'decoded')])
        source = json.loads(self.query(self.derived, 'SELECT source FROM processing')[0][0])
        self.assertEqual(source['kind'], 'legacy-prefix')

    def test_source_error_truncation_wrong_length_and_bad_profile_are_invalid(self):
        bad = bytearray(payload()); bad[16:20] = b'bad!'
        wire = pipeline.MAGIC + b''.join([
            pipeline.encode_frame(payload(), truncated=True),
            pipeline.encode_frame(payload(), receive_error='ENOBUFS'),
            pipeline.encode_frame(b'partial'), pipeline.encode_frame(bytes(bad))])
        self.ingest(wire)
        self.assertEqual(pipeline.process(self.raw, self.derived),
                         dict(status='partial', frames=4, invalid_frames=4))
        self.assertEqual(self.original_bytes(), wire)

    def test_actual_sqlite_full_retains_previous_transaction(self):
        original = pipeline._commit_chunk
        def limited(connection, seq, offset, raw, digest):
            if seq == 1:
                pages = connection.execute('PRAGMA page_count').fetchone()[0]
                connection.execute(f'PRAGMA max_page_count={pages}')
            original(connection, seq, offset, raw, digest)
        with patch.object(pipeline, '_commit_chunk', side_effect=limited):
            with self.assertRaisesRegex(sqlite3.OperationalError, 'full'):
                pipeline.ingest(Fragments([self.wire, b'x' * 65536]), self.raw, descriptor())
        self.assertEqual(self.original_bytes(), self.wire)
        self.assertNotEqual(self.query(self.raw, 'SELECT status FROM acquisition'), [('received',)])
        self.assertEqual(self.query(self.raw, 'PRAGMA integrity_check'), [('ok',)])

    def test_slow_processing_does_not_read_or_modify_acquisition(self):
        self.ingest()
        before = self.raw.read_bytes()
        original = pipeline.decoder.decode
        def delayed(value):
            # Acquisition has already committed and closed; decoder is independent.
            time.sleep(.03)
            self.assertEqual(self.raw.read_bytes(), before)
            return original(value)
        with patch.object(pipeline.decoder, 'decode', side_effect=delayed):
            pipeline.process(self.raw, self.derived)
        self.assertEqual(self.raw.read_bytes(), before)

    def test_decoder_exception_preserves_raw_and_fails_processing(self):
        self.ingest()
        before = self.raw.read_bytes()
        with patch.object(pipeline.decoder, 'decode', side_effect=RuntimeError('synthetic decoder failure')):
            with self.assertRaises(RuntimeError):
                pipeline.process(self.raw, self.derived)
        self.assertEqual(self.raw.read_bytes(), before)
        self.assertEqual(self.query(self.derived, 'SELECT status FROM processing'), [('failed',)])

    def test_empty_and_invalid_envelopes_fail_without_losing_input(self):
        for wire in (b'', pipeline.MAGIC, b'badmagic', pipeline.MAGIC + b'\x00',
                     pipeline.MAGIC + struct.pack('<II', 4097, 1)):
            with self.subTest(wire=wire):
                folder = self.root / str(len(list(self.root.iterdir())))
                folder.mkdir()
                raw, derived = folder / 'raw.db', folder / 'derived.db'
                pipeline.ingest(io.BytesIO(wire), raw, descriptor())
                with self.assertRaises(ValueError):
                    pipeline.process(raw, derived)
                self.assertEqual(b''.join(r[0] for r in self.query(raw, 'SELECT raw FROM chunks ORDER BY seq')), wire)

    def test_byte_budget_retains_last_read_and_raises(self):
        with self.assertRaisesRegex(ValueError, 'budget exceeded'):
            pipeline.ingest(io.BytesIO(self.wire), self.raw, descriptor(), max_bytes=1)
        self.assertEqual(self.original_bytes(), self.wire)

    def test_existing_outputs_are_never_overwritten(self):
        self.raw.write_bytes(b'keep existing history')
        with self.assertRaises(FileExistsError):
            self.ingest()
        self.assertEqual(self.raw.read_bytes(), b'keep existing history')

    def test_corrupt_journal_is_rejected_before_output_creation(self):
        self.ingest()
        with closing(sqlite3.connect(self.raw)) as connection, connection:
            connection.execute("UPDATE chunks SET raw=zeroblob(length(raw))")
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            pipeline.process(self.raw, self.derived)
        self.assertFalse(self.derived.exists())

    def test_running_journal_and_same_path_output_rejected(self):
        self.ingest()
        with self.assertRaises(FileExistsError):
            pipeline.process(self.raw, self.raw)
        with closing(sqlite3.connect(self.raw)) as connection, connection:
            connection.execute("UPDATE acquisition SET status='running'")
        with self.assertRaisesRegex(ValueError, 'terminal acquisition'):
            pipeline.process(self.raw, self.derived)

    def test_duplicate_header_and_invalid_clock_fail(self):
        header = b'{"source_sequence":null,"source_sequence":1}'
        self.ingest(pipeline.MAGIC + struct.pack('<II', len(header), 0) + header)
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            pipeline.process(self.raw, self.derived)
        for value in (-1, True, 2**63, 1.5):
            with self.assertRaises(ValueError):
                pipeline.encode_frame(payload(), source_monotonic_ns=value)

    def test_cli_file_roundtrip_and_existing_derived_refusal(self):
        wire = self.root / 'input.bin'
        source = self.root / 'source.json'
        wire.write_bytes(self.wire)
        source.write_text(json.dumps(descriptor()), encoding='utf-8')
        script = Path(__file__).resolve().parents[1] / 'scripts/raw_pipeline.py'
        received = subprocess.run([sys.executable, str(script), 'ingest', '--input', str(wire),
                                   '--source', str(source), '--output', str(self.raw)],
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(received.returncode, 0, received.stderr)
        self.assertEqual(json.loads(received.stdout)['bytes'], len(self.wire))
        processed = subprocess.run([sys.executable, str(script), 'process', '--raw', str(self.raw),
                                    '--output', str(self.derived)],
                                   capture_output=True, text=True, timeout=10)
        self.assertEqual(processed.returncode, 0, processed.stderr)
        self.assertEqual(json.loads(processed.stdout)['frames'], 1)
        before = self.derived.read_bytes()
        with self.assertRaises(FileExistsError):
            pipeline.process(self.raw, self.derived)
        self.assertEqual(self.derived.read_bytes(), before)

    def test_invalid_source_does_not_create_database(self):
        source = descriptor()
        source['origin'] = 'live-device'
        with self.assertRaises(ValueError):
            self.ingest(source=source)
        self.assertFalse(self.raw.exists())

    def test_failure_events_keep_traceback_without_record_bytes(self):
        with self.assertRaises(ConnectionError):
            pipeline.ingest(Fragments([self.wire], ConnectionError('synthetic disconnect')),
                            self.raw, descriptor())
        events = self.query(self.raw, 'SELECT event,details FROM events ORDER BY seq')
        self.assertEqual([row[0] for row in events], ['ingestion_started', 'ingestion_failed'])
        detail = json.loads(events[-1][1])
        self.assertIn('ConnectionError: synthetic disconnect', detail['traceback'])
        self.assertEqual(detail['committed_bytes'], len(self.wire))
        self.assertNotIn(payload().hex(), events[-1][1])


if __name__ == '__main__':
    unittest.main()
