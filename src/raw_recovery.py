"""Bounded local recovery/import into new journals; never edits the source DB."""
from contextlib import closing, contextmanager
import hashlib
import logging
from pathlib import Path
import sqlite3
import struct
import time

import decoder
import raw_pipeline as raw

MAX_BYTES = 64 * 1024**2
MAX_ROWS = 100000
MAX_EVENTS = 10000
MAX_DIAGNOSTICS = 16 * 1024**2
LOG = logging.getLogger('ruview.raw_recovery')


@contextmanager
def snapshot(path, timeout_s):
    """Bound SQLite work/waits; filesystem I/O is not a hard real-time deadline."""
    if not isinstance(timeout_s, (int, float)) or not 0 < timeout_s <= 300:
        raise ValueError('timeout_s must be in (0, 300]')
    # Never ignore a WAL or ask SQLite to repair a potentially hot journal.
    # Use a quiescent offline copy; sidecar removal/checkpointing is not our job.
    path = Path(path)
    if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('SQLite sidecar present; use a clean offline snapshot, do not delete sidecars')
    deadline = time.monotonic() + timeout_s
    with closing(raw._readonly(path)) as connection:
        connection.execute('PRAGMA busy_timeout=1000')
        connection.execute('PRAGMA trusted_schema=OFF')
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        connection.execute('BEGIN')
        def check():
            if time.monotonic() >= deadline:
                raise TimeoutError('Offline operation deadline exceeded')
        yield connection, check


def _limits(max_bytes, max_rows):
    if type(max_bytes) is not int or max_bytes <= 0 or type(max_rows) is not int or max_rows <= 0:
        raise ValueError('Byte and row limits must be positive integers')


def recover(input_path, output, *, max_bytes=MAX_BYTES, max_rows=MAX_ROWS, timeout_s=30):
    """Copy verified committed chunks/events; retain failed status and the entire tail.

    This recovers a readable application journal, not damaged SQLite pages or
    uncommitted writes. A source needing SQLite hot-journal repair is not edited.
    """
    _limits(max_bytes, max_rows)
    LOG.info('Offline recovery started output=%s', output)
    with snapshot(input_path, timeout_s) as (source, check):
        if source.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('Unsupported raw journal version')
        descriptors = source.execute('SELECT length(cast(source AS BLOB)) FROM acquisition LIMIT 2').fetchall()
        if len(descriptors) != 1 or descriptors[0][0] is None or descriptors[0][0] > raw.MAX_HEADER:
            raise ValueError('Invalid recovery descriptor size/count')
        acquisitions = source.execute('SELECT source,status,bytes,sha256 FROM acquisition LIMIT 2').fetchall()
        if len(acquisitions) != 1 or acquisitions[0][1] != 'running':
            raise ValueError('Recovery requires exactly one running acquisition')
        descriptor, _, expected_bytes, expected_hash = acquisitions[0]
        raw.validate_source(raw._load_json(descriptor))
        chunks, total, largest = source.execute(
            'SELECT count(*),coalesce(sum(length(raw)),0),coalesce(max(length(raw)),0) FROM chunks').fetchone()
        if chunks > max_rows or total > max_bytes or largest > raw.CHUNK_SIZE:
            raise ValueError('Recovery chunk/byte limit exceeded')
        events, event_bytes, largest_event = source.execute(
            'SELECT count(*),coalesce(sum(length(cast(details AS BLOB))),0),'
            'coalesce(max(length(cast(event AS BLOB))),0) FROM events').fetchone()
        if events > MAX_EVENTS or event_bytes > MAX_DIAGNOSTICS or largest_event > 128:
            raise ValueError('Recovery diagnostic limit exceeded')
        digest, verified_bytes = hashlib.sha256(), 0
        for chunk in raw._chunks(source):
            check()
            digest.update(chunk)
            verified_bytes += len(chunk)
        if verified_bytes != expected_bytes or digest.hexdigest() != expected_hash:
            raise ValueError('Recovery integrity mismatch; no salvage or truncation attempted')
        if source.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity failure; recovery refused')
        previous_clock = -1
        for clock, in source.execute('SELECT arrival_monotonic_ns FROM chunks ORDER BY seq'):
            check()
            if type(clock) is not int or clock < 0 or clock < previous_clock:
                raise ValueError('Invalid journal arrival clock')
            previous_clock = clock
        # Validate diagnostics before copying; do not silently discard malformed events.
        for _, utc, event, detail in source.execute('SELECT * FROM events ORDER BY seq'):
            check()
            if not isinstance(utc, (int, float)) or not isinstance(event, str) or not isinstance(raw._load_json(detail), dict):
                raise ValueError('Invalid source event')
        check()
        with closing(raw._create(output, raw.RAW_SCHEMA, 1)) as target:
            # Atomic copy: if interrupted/full, a partial destination has no terminal row.
            with target:
                target.execute('INSERT INTO acquisition VALUES (?,?,?,?,?)',
                               (descriptor, 'failed', expected_bytes, expected_hash, 'InterruptedAcquisition'))
                for row in source.execute('SELECT * FROM chunks ORDER BY seq'):
                    check()
                    target.execute('INSERT INTO chunks VALUES (?,?,?,?)', row)
                for row in source.execute('SELECT * FROM events ORDER BY seq'):
                    check()
                    target.execute('INSERT INTO events VALUES (?,?,?,?)', row)
                raw._event(target, 'recovered_interrupted_snapshot', original_status='running',
                           raw_sha256=expected_hash, committed_bytes=expected_bytes,
                           source_descriptor_sha256=hashlib.sha256(descriptor.encode()).hexdigest(),
                           uncommitted_bytes='unknown', completion_confirmed=False)
            check()
    LOG.info('Recovered committed snapshot bytes=%d chunks=%d completion=unknown', expected_bytes, chunks)
    return {'status': 'recovered-partial', 'bytes': expected_bytes, 'chunks': chunks}


class _EnvelopeStream:
    def __init__(self, rows, expected_size, check):
        self.rows = iter(rows)
        self.expected_size = expected_size
        self.check = check
        self.buffer = bytearray(raw.MAGIC)
        self.done = False

    def read(self, size):
        self.check()
        while len(self.buffer) < size and not self.done:
            try:
                seq, payload = next(self.rows)
            except StopIteration:
                self.done = True
                break
            self.check()
            self.buffer.extend(raw.encode_frame(payload, source_sequence=seq,
                                               truncated=len(payload) != self.expected_size))
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result


def import_legacy(input_path, session_id, output, descriptor, *, max_bytes=MAX_BYTES,
                  max_rows=MAX_ROWS, timeout_s=30):
    """Import one existing GT SQLite session, preserving its BLOBs and provenance.

    Caller declares payload vs prefix. Known opposite lengths are refused, not
    relabeled. Other short records are preserved with a truncation indication.
    """
    _limits(max_bytes, max_rows)
    raw.validate_source(descriptor)
    if (descriptor['origin'] != 'offline-import' or descriptor['device'] != 'GT-AX11000'
            or descriptor['profile'] != decoder.PROFILE
            or descriptor['kind'] not in {'csimond-payload', 'legacy-prefix'}):
        raise ValueError('Import requires explicit offline GT profile and payload/prefix kind')
    expected_size = 2048 if descriptor['kind'] == 'csimond-payload' else 320
    LOG.info('Offline legacy import started output=%s', output)
    with snapshot(input_path, timeout_s) as (source, check):
        # Length preflight avoids materializing unrestricted logs/metadata/BLOBs.
        summary = source.execute('SELECT status,length(cast(metadata AS BLOB)),length(cast(log AS BLOB)) '
                                 'FROM sessions WHERE id=?', (session_id,)).fetchall()
        if len(summary) != 1:
            raise ValueError('Expected exactly one legacy session')
        legacy_status, meta_size, log_size = summary[0]
        if meta_size is None or meta_size > 65536 or (log_size or 0) > 8 * 1024**2:
            raise ValueError('Legacy metadata/diagnostic size limit exceeded')
        if legacy_status not in {'captured', 'failed', 'running', 'paused', 'stopped'}:
            raise ValueError('Unsupported legacy session status')
        record_count, total, largest = source.execute(
            'SELECT count(*),coalesce(sum(length(raw)),0),coalesce(max(length(raw)),0) '
            'FROM records WHERE session=?', (session_id,)).fetchone()
        if not 0 < record_count <= max_rows or total > max_bytes or largest > expected_size:
            raise ValueError('Legacy record count/size limit exceeded')
        row = source.execute('SELECT id,started,finished,status,metadata,log FROM sessions WHERE id=?',
                             (session_id,)).fetchone()
        if not isinstance(row[4], str) or (row[5] is not None and not isinstance(row[5], str)):
            raise ValueError('Legacy metadata/log must be text (log may be null)')
        metadata = raw._load_json(row[4])
        if not isinstance(metadata, dict) or metadata.get('decoder') != decoder.PROFILE:
            raise ValueError('Legacy session does not declare the supported GT decoder profile')
        for field in ('interface', 'peer'):
            supplied, saved = descriptor[field], metadata.get(field)
            if supplied is not None and saved is not None and supplied.lower() != str(saved).lower():
                raise ValueError('Legacy source descriptor mismatch: ' + field)
        digest, previous, short = hashlib.sha256(), -1, 0
        for seq, payload in source.execute('SELECT seq,raw FROM records WHERE session=? ORDER BY seq', (session_id,)):
            check()
            if type(seq) is not int or not previous < seq < 2**63 or not isinstance(payload, bytes):
                raise ValueError('Invalid legacy record sequence/type')
            previous = seq
            if len(payload) == 320 and expected_size == 2048:
                raise ValueError('320-byte prefixes must not be imported as full payloads; select a homogeneous session')
            short += len(payload) != expected_size
            # Length-delimited digest binds source sequence to exact legacy bytes.
            digest.update(struct.pack('<QI', seq, len(payload)))
            digest.update(payload)
        provenance = {'format': 'legacy-gt-sqlite-session-v1',
                      'session': dict(zip(('id', 'started', 'finished', 'status', 'metadata', 'log'), row)),
                      'records': record_count, 'raw_bytes': total, 'short_records': short,
                      'records_sha256': digest.hexdigest(),
                      'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'clock': 'import arrival only; source clock unavailable', 'loss': None}
        check()
        rows = source.execute('SELECT seq,raw FROM records WHERE session=? ORDER BY seq', (session_id,))
        # Envelope overhead is bounded separately from the caller's raw-byte budget.
        wire_budget = total + record_count * (raw.MAX_HEADER + 8) + len(raw.MAGIC)
        result = raw.ingest(_EnvelopeStream(rows, expected_size, check), output, descriptor,
                            max_bytes=wire_budget, provenance=provenance,
                            upstream_complete=legacy_status == 'captured' and short == 0)
        return {**result, 'records': record_count, 'short_records': short,
                'legacy_status': legacy_status}
