"""Offline raw journal and independent replay; no device or network operations.

See docs/RAW-PIPELINE.md. Each output is a new database, never operational history.
"""
from contextlib import closing
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import struct
import time
import traceback

import decoder

LOG = logging.getLogger('ruview.raw_pipeline')
MAGIC = b'RUVRAW1\n'
CHUNK_SIZE = 65536
MAX_HEADER = 4096
MAX_PAYLOAD = 65536
KINDS = {'netlink-datagram', 'csimond-payload', 'legacy-prefix'}
SOURCE_FIELDS = {'source_id', 'device', 'interface', 'peer', 'firmware',
                 'profile', 'operation_id', 'layout_revision', 'configuration',
                 'kind', 'origin'}


def _json(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':'))


def _load_json(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=unique)


def validate_source(source):
    if not isinstance(source, dict) or set(source) != SOURCE_FIELDS:
        raise ValueError('Source descriptor requires exactly the documented fields')
    if source['kind'] not in KINDS or source['origin'] not in {'synthetic', 'offline-import'}:
        raise ValueError('Unsupported source kind/origin for offline prototype')
    for key in SOURCE_FIELDS - {'configuration'}:
        if source[key] is not None and (not isinstance(source[key], str) or not source[key]):
            raise ValueError('Source field must be a nonempty string or null: ' + key)
    if not source['source_id'] or not source['operation_id']:
        raise ValueError('source_id and operation_id are required')
    if not isinstance(source['configuration'], dict):
        raise ValueError('configuration must be an object without credentials')
    if len(_json(source).encode()) > MAX_HEADER:
        raise ValueError('Source descriptor too large')


def _validate_header(header):
    if not isinstance(header, dict) or set(header) != {
        'source_sequence', 'source_monotonic_ns', 'truncated', 'receive_error'
    }:
        raise ValueError('Invalid frame metadata fields')
    for key in ('source_sequence', 'source_monotonic_ns'):
        value = header[key]
        if value is not None and (type(value) is not int or not 0 <= value < 2**63):
            raise ValueError('Invalid source counter/clock')
    if type(header['truncated']) is not bool:
        raise ValueError('truncated must be Boolean')
    error = header['receive_error']
    if error is not None and (not isinstance(error, str) or not 0 < len(error) <= 128):
        raise ValueError('Invalid receive error code')


def encode_frame(payload, *, source_sequence=None, source_monotonic_ns=None,
                 truncated=False, receive_error=None):
    """Fixture/import envelope; sequence is a reader counter, never driver loss."""
    if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD:
        raise ValueError('Payload must be bounded bytes')
    header = dict(source_sequence=source_sequence, source_monotonic_ns=source_monotonic_ns,
                  truncated=truncated, receive_error=receive_error)
    _validate_header(header)
    encoded = _json(header).encode('utf-8')
    return struct.pack('<II', len(encoded), len(payload)) + encoded + payload


def _create(path, schema, version):
    path = Path(path)
    # Exclusive reservation prevents SQLite from opening or migrating an existing DB.
    with path.open('xb'):
        pass
    connection = sqlite3.connect(path)
    try:
        connection.execute('PRAGMA synchronous=FULL')
        connection.executescript(schema)
        connection.execute(f'PRAGMA user_version={version}')
        connection.commit()
        return connection
    except BaseException:
        connection.close()
        raise


def _readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def _event(connection, event, **details):
    connection.execute('INSERT INTO events (utc_seconds,event,details) VALUES (?,?,?)',
                       (time.time(), event, _json(details)))


EVENT_SCHEMA = '''
CREATE TABLE events (seq INTEGER PRIMARY KEY, utc_seconds REAL NOT NULL,
    event TEXT NOT NULL, details TEXT NOT NULL);
'''


def _commit_chunk(connection, seq, offset, raw, digest):
    with connection:
        connection.execute('INSERT INTO chunks VALUES (?,?,?,?)',
                           (seq, offset, time.monotonic_ns(), raw))
        connection.execute('UPDATE acquisition SET bytes=?, sha256=?',
                           (offset + len(raw), digest))


def ingest(stream, output, source, *, max_bytes=64 * 1024**2):
    """Commit bounded read() chunks before any parsing. EOF is transport completion only.

    Prior commits survive a failure. The current uncommitted chunk cannot be
    guaranteed on disk-full; failure is raised, never converted into success.
    """
    validate_source(source)
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError('max_bytes must be positive')
    schema = '''
    CREATE TABLE acquisition (source TEXT NOT NULL, status TEXT NOT NULL,
        bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, error TEXT);
    CREATE TABLE chunks (seq INTEGER PRIMARY KEY, offset INTEGER NOT NULL,
        arrival_monotonic_ns INTEGER NOT NULL, raw BLOB NOT NULL);
    ''' + EVENT_SCHEMA
    count, seq, digest = 0, 0, hashlib.sha256()
    with closing(_create(output, schema, 1)) as connection:
        with connection:
            connection.execute('INSERT INTO acquisition VALUES (?,?,?,?,NULL)',
                               (_json(source), 'running', 0, digest.hexdigest()))
            _event(connection, 'ingestion_started', max_bytes=max_bytes,
                   time_basis='local-import-monotonic-not-rf')
        LOG.info('Offline ingestion started output=%s', output)
        try:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not isinstance(chunk, bytes) or len(chunk) > CHUNK_SIZE:
                    raise ValueError('Input must provide bounded blocking binary reads')
                if not chunk:
                    break
                digest.update(chunk)
                _commit_chunk(connection, seq, count, chunk, digest.hexdigest())
                count += len(chunk)
                seq += 1
                # Preserve the last returned chunk even if it crosses the budget.
                if count > max_bytes:
                    raise ValueError('Input byte budget exceeded; last read retained')
            with connection:
                connection.execute("UPDATE acquisition SET status='received'")
                _event(connection, 'input_eof', committed_bytes=count, chunks=seq)
        except BaseException as exc:
            LOG.exception('Offline ingestion failed output=%s committed_bytes=%d', output, count)
            try:
                with connection:
                    connection.execute("UPDATE acquisition SET status='failed', error=?",
                                       (type(exc).__name__,))
                    _event(connection, 'ingestion_failed', committed_bytes=count,
                           error_type=type(exc).__name__, traceback=traceback.format_exc())
            except sqlite3.Error:
                LOG.exception('Cannot persist failure status; journal must not be treated as complete')
            raise
    LOG.info('Offline ingestion received bytes=%d chunks=%d', count, seq)
    return {'status': 'received', 'bytes': count, 'chunks': seq}


def _chunks(connection):
    offset = 0
    for seq, row in enumerate(connection.execute('SELECT seq,offset,raw FROM chunks ORDER BY seq')):
        number, saved_offset, raw = row
        if number != seq or saved_offset != offset or not isinstance(raw, bytes) or not 0 < len(raw) <= CHUNK_SIZE:
            raise ValueError('Corrupt raw chunk sequence/length')
        offset += len(raw)
        yield raw


class _Reader:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.buffer = bytearray()
        self.offset = 0

    def take(self, size, *, eof_ok=False):
        while len(self.buffer) < size:
            try:
                self.buffer.extend(next(self.chunks))
            except StopIteration:
                if eof_ok and not self.buffer:
                    return None
                raise ValueError(f'Incomplete envelope at byte {self.offset}') from None
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        self.offset += size
        return result


def _frames(connection):
    reader = _Reader(_chunks(connection))
    if reader.take(len(MAGIC)) != MAGIC:
        raise ValueError('Unknown envelope magic/version')
    while True:
        offset = reader.offset
        prefix = reader.take(8, eof_ok=True)
        if prefix is None:
            return
        header_size, size = struct.unpack('<II', prefix)
        if not 0 < header_size <= MAX_HEADER or size > MAX_PAYLOAD:
            raise ValueError(f'Invalid envelope lengths at byte {offset}')
        header = _load_json(reader.take(header_size).decode('utf-8'))
        _validate_header(header)
        payload_offset = reader.offset
        payload = reader.take(size)
        yield offset, payload_offset, header, payload


def _interpret(source, header, payload):
    if header['truncated'] or header['receive_error'] is not None:
        return 'invalid', {'reason': 'source_receive_failure'}
    expected = {'netlink-datagram': 2064, 'csimond-payload': 2048, 'legacy-prefix': 320}[source['kind']]
    if len(payload) != expected:
        return 'invalid', {'reason': 'unexpected_length', 'expected': expected}
    # No repeater format or full Netlink decoder has been validated.
    if source['kind'] == 'netlink-datagram' or source['profile'] != decoder.PROFILE:
        return 'raw-only', {'reason': 'unsupported_profile_or_transport'}
    try:
        return 'decoded', decoder.decode(payload)
    except ValueError:
        return 'invalid', {'reason': 'profile_rejected_payload'}


def process(raw_path, output):
    """Replay a terminal journal read-only into a separate new derived database.

    No polling, input queue or acquisition callback: decoding can run much later.
    """
    with closing(_readonly(raw_path)) as raw:
        raw.execute('BEGIN')  # One stable snapshot for integrity checking and replay.
        if raw.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('Unsupported raw journal version')
        rows = raw.execute('SELECT source,status,bytes,sha256 FROM acquisition').fetchall()
        if len(rows) != 1 or rows[0][1] not in {'received', 'failed'}:
            raise ValueError('Raw journal must have one terminal acquisition')
        source_json, raw_status, byte_count, expected_hash = rows[0]
        source = _load_json(source_json)
        validate_source(source)
        digest, count = hashlib.sha256(), 0
        for chunk in _chunks(raw):
            digest.update(chunk)
            count += len(chunk)
        if count != byte_count or digest.hexdigest() != expected_hash:
            raise ValueError('Raw journal integrity mismatch')
        schema = '''
        CREATE TABLE processing (source TEXT, raw_sha256 TEXT, raw_status TEXT,
            decoder_sha256 TEXT, pipeline_sha256 TEXT, status TEXT, error TEXT);
        CREATE TABLE frames (seq INTEGER PRIMARY KEY, envelope_offset INTEGER,
            payload_offset INTEGER, payload_bytes INTEGER, metadata TEXT,
            status TEXT, result TEXT);
        ''' + EVENT_SCHEMA
        decoder_hash = hashlib.sha256(Path(decoder.__file__).read_bytes()).hexdigest()
        pipeline_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        invalid, frames = 0, 0
        with closing(_create(output, schema, 1)) as derived:
            with derived:
                derived.execute('INSERT INTO processing VALUES (?,?,?,?,?,?,NULL)',
                                (source_json, expected_hash, raw_status, decoder_hash, pipeline_hash, 'running'))
                _event(derived, 'processing_started', raw_status=raw_status)
            try:
                for seq, (offset, payload_offset, header, payload) in enumerate(_frames(raw)):
                    status, result = _interpret(source, header, payload)
                    with derived:
                        derived.execute('INSERT INTO frames VALUES (?,?,?,?,?,?,?)',
                                        (seq, offset, payload_offset, len(payload), _json(header), status, _json(result)))
                    invalid += status == 'invalid'
                    frames += 1
                if not frames:
                    raise ValueError('Envelope contains no frames')
                status = 'partial' if raw_status == 'failed' or invalid else 'processed'
                with derived:
                    derived.execute('UPDATE processing SET status=?', (status,))
                    _event(derived, 'processing_finished', status=status, frames=frames, invalid=invalid)
            except BaseException as exc:
                LOG.exception('Offline processing failed output=%s retained_frames=%d', output, frames)
                try:
                    with derived:
                        derived.execute("UPDATE processing SET status='failed', error=?", (type(exc).__name__,))
                        _event(derived, 'processing_failed', retained_frames=frames,
                               error_type=type(exc).__name__, traceback=traceback.format_exc())
                except sqlite3.Error:
                    LOG.exception('Cannot persist processing failure status')
                raise
    return {'status': status, 'frames': frames, 'invalid_frames': invalid}
