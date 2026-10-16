"""Recovery/import tests on generated local databases, never lab history."""
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
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import raw_pipeline as raw
import raw_recovery as recovery
from test_raw_pipeline import descriptor, payload


class RecoveryImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / 'input.db'
        self.output = self.root / 'output.db'
        self.derived = self.root / 'derived.db'
        self.wire = raw.MAGIC + raw.encode_frame(payload())

    def query(self, path, sql, parameters=()):
        with closing(sqlite3.connect(path)) as connection:
            return connection.execute(sql, parameters).fetchall()

    def modify(self, sql, parameters=()):
        with closing(sqlite3.connect(self.input)) as connection, connection:
            connection.execute(sql, parameters)

    def running(self, wire=None):
        raw.ingest(io.BytesIO(self.wire if wire is None else wire), self.input, descriptor())
        self.modify("UPDATE acquisition SET status='running'")
        # Model interruption before the terminal transaction, not a completed EOF.
        self.modify("DELETE FROM events WHERE event='input_eof'")

    def import_source(self, kind='csimond-payload'):
        source = descriptor(kind=kind)
        source.update(origin='offline-import', device='GT-AX11000')
        return source

    def legacy(self, records=None, status='captured'):
        if records is None:
            records = [(0, payload()), (3, payload())]
        metadata = json.dumps({'decoder': raw.decoder.PROFILE, 'interface': 'eth6', 'peer': 'AA:BB:CC:DD:EE:00'})
        with closing(sqlite3.connect(self.input)) as connection, connection:
            connection.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY,started REAL,finished REAL,status TEXT,metadata TEXT,log TEXT)')
            connection.execute('CREATE TABLE records (session TEXT,seq INTEGER,raw BLOB,decoded TEXT,PRIMARY KEY(session,seq))')
            connection.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',
                               ('fixture', 10, 20, status, metadata, 'full synthetic diagnostics\nline two'))
            connection.executemany('INSERT INTO records VALUES (?,?,?,?)',
                                   [('fixture', seq, value, '{}') for seq, value in records])

    def imported_frames(self):
        # Independent unpacking of the envelope, not the production frame parser.
        wire = b''.join(row[0] for row in self.query(self.output, 'SELECT raw FROM chunks ORDER BY seq'))
        self.assertEqual(wire[:8], b'RUVRAW1\n')
        offset, frames = 8, []
        while offset < len(wire):
            meta_size, size = struct.unpack_from('<II', wire, offset)
            offset += 8
            header = json.loads(wire[offset:offset+meta_size])
            offset += meta_size
            frames.append((header, wire[offset:offset+size]))
            offset += size
        self.assertEqual(offset, len(wire))
        return frames

    def test_recovery_preserves_bytes_clocks_events_and_forces_partial(self):
        self.running()
        before = self.input.read_bytes()
        result = recovery.recover(self.input, self.output)
        self.assertEqual(result['status'], 'recovered-partial')
        self.assertEqual(self.input.read_bytes(), before)
        self.assertEqual(self.query(self.input, 'SELECT * FROM chunks'), self.query(self.output, 'SELECT * FROM chunks'))
        original_events = self.query(self.input, 'SELECT * FROM events ORDER BY seq')
        self.assertEqual(self.query(self.output, 'SELECT * FROM events ORDER BY seq')[:-1], original_events)
        self.assertEqual(raw.process(self.output, self.derived)['status'], 'partial')

    def test_real_process_exit_after_committed_chunk_is_recoverable(self):
        fixture = self.root / 'fixture.bin'
        fixture.write_bytes(self.wire)
        script = self.root / 'exit_fixture.py'
        source_dir = str(Path(raw.__file__).parent)
        script.write_text(
            'import sys, os\nfrom pathlib import Path\n'
            f'sys.path.insert(0, {source_dir!r})\nimport raw_pipeline\n'
            'class Input:\n'
            '    first = True\n'
            '    def read(self, size):\n'
            '        if not self.first: os._exit(73)\n'
            '        self.first = False\n'
            f'        return Path({str(fixture)!r}).read_bytes()\n'
            f'raw_pipeline.ingest(Input(), {str(self.input)!r}, {descriptor()!r})\n', encoding='utf-8')
        child = subprocess.run([sys.executable, str(script)], capture_output=True, timeout=10)
        self.assertEqual(child.returncode, 73)
        self.assertEqual(self.query(self.input, 'SELECT status FROM acquisition'), [('running',)])
        before = hashlib.sha256(self.input.read_bytes()).hexdigest()
        recovery.recover(self.input, self.output)
        self.assertEqual(hashlib.sha256(self.input.read_bytes()).hexdigest(), before)
        self.assertEqual(raw.process(self.output, self.derived)['status'], 'partial')

    def test_recovery_never_discards_incomplete_tail(self):
        wire = self.wire + raw.encode_frame(payload())[:-15]
        self.running(wire)
        recovery.recover(self.input, self.output)
        copied = b''.join(r[0] for r in self.query(self.output, 'SELECT raw FROM chunks ORDER BY seq'))
        self.assertEqual(copied, wire)
        with self.assertRaisesRegex(ValueError, 'Incomplete envelope'):
            raw.process(self.output, self.derived)
        self.assertEqual(self.query(self.derived, 'SELECT count(*) FROM frames'), [(1,)])

    def test_recovery_corruption_and_budget_refused_before_output(self):
        self.running()
        with self.assertRaisesRegex(ValueError, 'limit exceeded'):
            recovery.recover(self.input, self.output, max_bytes=1)
        self.assertFalse(self.output.exists())
        self.modify("UPDATE chunks SET raw=zeroblob(length(raw))")
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            recovery.recover(self.input, self.output)
        self.assertFalse(self.output.exists())

    def test_recovery_invalid_clock_refused(self):
        self.running()
        self.modify('UPDATE chunks SET arrival_monotonic_ns=-1')
        with self.assertRaisesRegex(ValueError, 'arrival clock'):
            recovery.recover(self.input, self.output)
        self.assertFalse(self.output.exists())

    def test_recovery_refuses_completed_journal_existing_file_and_deadline(self):
        self.running()
        with self.assertRaises(TimeoutError):
            recovery.recover(self.input, self.output, timeout_s=0.00000001)
        self.assertFalse(self.output.exists())
        self.output.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            recovery.recover(self.input, self.output)
        self.assertEqual(self.output.read_bytes(), b'preserve')
        self.modify("UPDATE acquisition SET status='received'")
        with self.assertRaisesRegex(ValueError, 'running acquisition'):
            recovery.recover(self.input, self.derived)

    def test_recovery_copy_failure_has_no_successful_terminal_row(self):
        self.running()
        original = raw._event
        def fail_recovery(connection, event, **details):
            if event == 'recovered_interrupted_snapshot':
                raise sqlite3.OperationalError('synthetic storage failure')
            return original(connection, event, **details)
        with patch.object(raw, '_event', side_effect=fail_recovery):
            with self.assertRaises(sqlite3.OperationalError):
                recovery.recover(self.input, self.output)
        self.assertEqual(self.query(self.output, 'SELECT count(*) FROM acquisition'), [(0,)])
        with self.assertRaises(ValueError):
            raw.process(self.output, self.derived)

    def test_import_exact_payloads_sparse_sequences_and_provenance(self):
        self.legacy()
        before = self.input.read_bytes()
        result = recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertEqual(result['status'], 'received')
        self.assertEqual(result['records'], 2)
        frames = self.imported_frames()
        self.assertEqual([h['source_sequence'] for h, _ in frames], [0, 3])
        self.assertTrue(all(h['source_monotonic_ns'] is None for h, _ in frames))
        self.assertEqual([p for _, p in frames], [payload(), payload()])
        self.assertEqual(self.input.read_bytes(), before)
        detail = json.loads(self.query(self.output, "SELECT details FROM events WHERE event='import_provenance'")[0][0])
        self.assertEqual(detail['session']['log'], 'full synthetic diagnostics\nline two')
        self.assertIsNone(detail['loss'])
        self.assertEqual(raw.process(self.output, self.derived)['frames'], 2)
        iq = json.loads(self.query(self.derived, 'SELECT result FROM frames WHERE seq=0')[0][0])['iq']
        self.assertEqual(iq[0], [0, 1])
        self.assertEqual(iq[-1], [110, 111])

    def test_import_legacy_prefix_keeps_320_byte_identity(self):
        self.legacy([(0, payload(320))])
        recovery.import_legacy(self.input, 'fixture', self.output, self.import_source('legacy-prefix'))
        self.assertEqual(len(self.imported_frames()[0][1]), 320)
        raw.process(self.output, self.derived)
        self.assertEqual(self.query(self.derived, 'SELECT payload_bytes,status FROM frames'), [(320, 'decoded')])

    def test_import_crosses_multiple_ingestion_chunks_without_reordering(self):
        records = [(i * 2, payload()[:-4] + struct.pack('<I', i)) for i in range(70)]
        self.legacy(records)
        result = recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertGreater(result['chunks'], 1)
        frames = self.imported_frames()
        self.assertEqual([(h['source_sequence'], data) for h, data in frames], records)
        self.assertEqual(raw.process(self.output, self.derived)['frames'], 70)

    def test_import_known_prefix_cannot_be_relabeled_full(self):
        self.legacy([(0, payload(320))])
        with self.assertRaisesRegex(ValueError, 'prefixes must not'):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertFalse(self.output.exists())

    def test_import_short_records_and_original_failure_remain_partial(self):
        self.legacy([(0, payload()), (1, b'partial')], status='failed')
        result = recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['short_records'], 1)
        self.assertEqual(self.imported_frames()[1][1], b'partial')
        self.assertTrue(self.imported_frames()[1][0]['truncated'])
        self.assertEqual(raw.process(self.output, self.derived)['status'], 'partial')

    def test_import_running_source_not_promoted_to_captured(self):
        self.legacy(status='running')
        result = recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(raw.process(self.output, self.derived)['status'], 'partial')

    def test_import_wrong_profile_source_empty_and_limits(self):
        self.legacy()
        for kwargs in ({'max_rows': 1}, {'max_bytes': 1}):
            with self.assertRaisesRegex(ValueError, 'limit exceeded'):
                recovery.import_legacy(self.input, 'fixture', self.output, self.import_source(), **kwargs)
        wrong = self.import_source(); wrong['device'] = 'RP-AX58'
        with self.assertRaises(ValueError):
            recovery.import_legacy(self.input, 'fixture', self.output, wrong)
        self.modify('UPDATE sessions SET metadata=?', (json.dumps({'decoder': 'unknown'}),))
        with self.assertRaisesRegex(ValueError, 'does not declare'):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertFalse(self.output.exists())

    def test_import_descriptor_conflict_and_empty_session_rejected(self):
        self.legacy()
        wrong = self.import_source(); wrong['interface'] = 'eth8'
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            recovery.import_legacy(self.input, 'fixture', self.output, wrong)
        self.modify('DELETE FROM records')
        with self.assertRaisesRegex(ValueError, 'count/size limit'):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertFalse(self.output.exists())

    def test_import_bad_sequence_and_nonblob_rejected(self):
        self.legacy([(-1, payload())])
        with self.assertRaisesRegex(ValueError, 'sequence/type'):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.modify("UPDATE records SET seq=0,raw='not a blob'")
        with self.assertRaisesRegex(ValueError, 'sequence/type'):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())

    def test_import_limits_oversized_log_without_copy(self):
        self.legacy()
        self.modify('UPDATE sessions SET log=zeroblob(?)', (8 * 1024**2 + 1,))
        with self.assertRaisesRegex(ValueError, 'diagnostic size limit'):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertFalse(self.output.exists())

    def test_cli_recovery_reports_partial_with_nonzero_exit(self):
        self.running()
        script = Path(__file__).resolve().parents[1] / 'scripts/raw_pipeline.py'
        result = subprocess.run([sys.executable, str(script), 'recover', '--raw', str(self.input),
                                 '--output', str(self.output)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'recovered-partial')

    def test_cli_import_roundtrip(self):
        self.legacy()
        source = self.root / 'source.json'
        source.write_text(json.dumps(self.import_source()), encoding='utf-8')
        script = Path(__file__).resolve().parents[1] / 'scripts/raw_pipeline.py'
        result = subprocess.run([sys.executable, str(script), 'import-legacy', '--history', str(self.input),
                                 '--session', 'fixture', '--source', str(source), '--output', str(self.output)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['records'], 2)

    def test_sqlite_sidecars_are_never_ignored_or_removed(self):
        self.running()
        sidecar = Path(str(self.input) + '-wal')
        sidecar.write_bytes(b'preserve unknown wal')
        before = self.input.read_bytes()
        with self.assertRaisesRegex(ValueError, 'sidecar present'):
            recovery.recover(self.input, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(sidecar.read_bytes(), b'preserve unknown wal')
        self.assertEqual(self.input.read_bytes(), before)

    def test_import_deadline_and_existing_output_protection(self):
        self.legacy()
        with self.assertRaises((TimeoutError, sqlite3.OperationalError)):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source(), timeout_s=0.00000001)
        self.assertFalse(self.output.exists())
        self.output.write_bytes(b'keep derived history')
        with self.assertRaises(FileExistsError):
            recovery.import_legacy(self.input, 'fixture', self.output, self.import_source())
        self.assertEqual(self.output.read_bytes(), b'keep derived history')


if __name__ == '__main__':
    unittest.main()
