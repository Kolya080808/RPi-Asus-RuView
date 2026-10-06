"""Local map, metadata and read-only CSI replay panel; Python standard library."""
import argparse
from collections import deque
from contextlib import closing
import datetime as dt
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import math
import mimetypes
from pathlib import Path
import re
import queue
import secrets
import shutil
import shlex
import sqlite3
import subprocess
import threading
import time
from urllib.parse import urlparse, parse_qs
import uuid

from panel_signal import measurements
from live_signal import LiveParser, LiveSignal
from decoder import decode, PROFILE

SRC = Path(__file__).resolve().parent
ROOT = SRC.parent if (SRC.parent / 'maps').is_dir() else SRC
MAP_DIR = ROOT / 'maps/home'
HISTORY = ROOT / 'history.sqlite3'
STATIC = ROOT / 'web'
MAX_BODY = 64 * 1024
MAX_RECORDS = 10000
WRITE_TOKEN = secrets.token_urlsafe(32)
LOGGER = logging.getLogger('ruview.panel')
ACTIVITIES = ('still', 'arm movement', 'walking', 'empty room', 'uncertain')
CAPTURE_MAX_SECONDS = 1800
CAPTURE_INTERVALS = (100, 200, 500)
# The CSI receiver is always GT-AX11000 eth6. This is its associated radio peer,
# not a collector running on that peer. Do not silently substitute another link.
CAPTURE_PEER = 'A0:36:BC:16:85:B9'
CAPTURE_LOCK = threading.RLock()
ACTIVE_CAPTURE = None
LATEST_CAPTURE = None


class RequestError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def db():
    connection = sqlite3.connect(HISTORY, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize():
    # Existing Pi schemas are unchanged. New local sandboxes use identical tables.
    with closing(db()) as connection, connection:
        connection.executescript('''
CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, started REAL, finished REAL, status TEXT, metadata TEXT, log TEXT);
CREATE TABLE IF NOT EXISTS records (session TEXT, seq INTEGER, raw BLOB, decoded TEXT, PRIMARY KEY(session,seq));
CREATE TABLE IF NOT EXISTS map_points (id TEXT PRIMARY KEY, label TEXT NOT NULL, region TEXT NOT NULL, x REAL NOT NULL, y REAL NOT NULL, height REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS map_routes (id TEXT PRIMARY KEY, label TEXT NOT NULL, region TEXT NOT NULL, points TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS session_annotations (id TEXT PRIMARY KEY, session TEXT NOT NULL, point_id TEXT, start_s REAL NOT NULL, end_s REAL, activity TEXT NOT NULL, source TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
''')


def router_script(seconds, interval):
    """Run one bounded router stream; EXIT always disables the temporary monitor."""
    if not 1 <= seconds <= CAPTURE_MAX_SECONDS or interval not in CAPTURE_INTERVALS:
        raise ValueError('Invalid capture bounds')
    return '''
set -e
[ "$(wl -i eth6 csimon state | sed -n 's/CSI Monitor: Enabled: //p')" = 0 ]
[ -z "$(wl -i eth6 csimon)" ]
[ -z "$(pidof csimond)" ]
wl -i eth6 assoclist | grep -qi 'PEER' || {
 echo 'Capture unavailable: configured peer PEER is not associated on GT-AX11000 eth6.'
 exit 4
}
collector_pid=
sleeper_pid=
cleanup() {
 set +e
 if [ -n "$sleeper_pid" ]; then kill "$sleeper_pid" 2>/dev/null; fi
 wl -i eth6 csimon disable
 wl -i eth6 csimon del PEER
 if [ -n "$collector_pid" ]; then kill "$collector_pid" 2>/dev/null || :; wait "$collector_pid" 2>/dev/null; fi
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
csimond 23 64 &
collector_pid=$!
sleep 1
wl -i eth6 csimon add PEER INTERVAL
wl -i eth6 csimon enable
echo RUVIEW_CAPTURE_STARTED
sleep SECONDS &
sleeper_pid=$!
wait "$sleeper_pid"
wl -i eth6 csimon state
'''.replace('PEER', CAPTURE_PEER).replace('INTERVAL', str(interval)).replace('SECONDS', str(seconds))


def router_command(seconds, interval):
    root = ROOT
    return ['ssh', '-tt', '-i', str(root / 'router_key'),
            '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'UserKnownHostsFile=' + str(root / 'router_known_hosts'),
            '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
            '-o', 'ServerAliveCountMax=2', 'admin@192.168.50.1',
            '/bin/sh -c ' + shlex.quote(router_script(seconds, interval))]


class CaptureJob:
    """A panel-owned bounded capture with resumable router segments."""
    def __init__(self, session, seconds, interval):
        self.session = session
        self.remaining = float(seconds)
        self.segment_started = None
        self.interval = interval
        self.stop_requested = threading.Event()
        self.resume_event = threading.Event()
        self.resume_event.set()
        self.pause_requested = False
        self.pause_ready = False
        self.process = None
        self.live_lock = threading.Lock()
        self.live_signal = LiveSignal(interval=interval / 1000, smoothing=1.0)
        self.live_samples = deque(maxlen=600)
        self.live_error = None
        self.last_received = None
        self.thread = threading.Thread(target=self.run, name='panel-capture', daemon=True)

    def start(self):
        self.thread.start()

    def remaining_seconds(self):
        with CAPTURE_LOCK:
            elapsed = 0 if self.segment_started is None else time.monotonic() - self.segment_started
            return max(0, round(self.remaining - elapsed, 1))

    def _freeze_clock(self):
        with CAPTURE_LOCK:
            if self.segment_started is not None:
                self.remaining = max(0, self.remaining - (time.monotonic() - self.segment_started))
                self.segment_started = None

    def request_pause(self):
        with CAPTURE_LOCK:
            if not self.thread.is_alive() or self.pause_requested or self.stop_requested.is_set():
                return False
            self.pause_requested = True
            self._freeze_clock()
            self.resume_event.clear()
            self._interrupt()
            return True

    def request_resume(self):
        with CAPTURE_LOCK:
            if not self.thread.is_alive() or not self.pause_ready or self.stop_requested.is_set():
                return False
            self.pause_requested = False
            self.pause_ready = False
            self.resume_event.set()
            return True

    def request_stop(self):
        self.stop_requested.set()
        self._freeze_clock()
        self.resume_event.set()
        self._interrupt()
        return True

    def _interrupt(self):
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.stdin.write(b'\x03')
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                process.terminate()

    def _set_status(self, status, finished=None, log=None):
        with closing(db()) as connection, connection:
            fields = ['status=?']
            values = [status]
            if finished is not None:
                fields.append('finished=?'); values.append(finished)
            if log is not None:
                fields.append('log=?'); values.append(log[-20000:])
            values.append(self.session)
            connection.execute('UPDATE sessions SET ' + ','.join(fields) + ' WHERE id=?', values)

    def _append(self, raw, seq):
        try:
            decoded = decode(raw)
        except ValueError as exc:
            decoded = {'error': str(exc)}
        with closing(db()) as connection, connection:
            connection.execute('INSERT INTO records VALUES (?,?,?,?)',
                               (self.session, seq, raw, json.dumps(decoded)))
        # Decode/filter each arriving record once, never the whole history per frame.
        with self.live_lock:
            try:
                point = self.live_signal.add(raw)
                self.live_samples.append({**point, 'seq': seq, 'valid': True})
                self.last_received = time.monotonic()
            except ValueError as exc:
                self.live_error = str(exc)
                self.live_samples.append({'seq': seq, 'valid': False, 'seconds': None})

    def live_payload(self, after):
        with self.live_lock:
            samples = list(self.live_samples)
            reset = after < 0 or bool(samples and after < samples[0]['seq'] - 1)
            return {'samples': samples if reset else [p for p in samples if p['seq'] > after],
                    'reset': reset, 'next_seq': samples[-1]['seq'] if samples else -1,
                    'last_sample_age_s': None if self.last_received is None else
                    round(time.monotonic() - self.last_received, 3),
                    'signal_error': self.live_error}

    def run(self):
        seq = 0
        with closing(db()) as connection:
            seq = connection.execute('SELECT count(*) FROM records WHERE session=?', (self.session,)).fetchone()[0]
        failure = None
        reader = None
        reader_cancel = threading.Event()
        try:
            while self.remaining > 0.25 and not self.stop_requested.is_set():
                if self.pause_requested:
                    self._set_status('paused')
                    with CAPTURE_LOCK:
                        self.pause_ready = True
                    self.resume_event.wait()
                    if self.stop_requested.is_set():
                        break
                    self._set_status('running')
                segment = max(1, math.ceil(min(self.remaining, CAPTURE_MAX_SECONDS)))
                parser = LiveParser()
                started = time.monotonic()
                command = router_command(segment, self.interval)
                with CAPTURE_LOCK:
                    if self.stop_requested.is_set() or self.pause_requested:
                        continue
                    self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                    stderr=subprocess.STDOUT)
                chunks = queue.Queue(maxsize=16)
                process = self.process
                reader_cancel.clear()
                def enqueue(value):
                    while not reader_cancel.is_set():
                        try:
                            chunks.put(value, timeout=.1)
                            return
                        except queue.Full:
                            continue
                def read_output():
                    try:
                        while not reader_cancel.is_set():
                            chunk = process.stdout.read1(65536)
                            if not chunk:
                                break
                            enqueue(chunk)
                    except Exception as exc:
                        enqueue(exc)
                    finally:
                        enqueue(None)
                reader = threading.Thread(target=read_output, name='capture-output', daemon=True)
                reader.start()
                output = deque(maxlen=32)
                interrupted_at = None
                segment_records = seq
                control_tail = ''
                capture_started = False
                while True:
                    now = time.monotonic()
                    if interrupted_at is None and (self.stop_requested.is_set() or self.pause_requested):
                        interrupted_at = now
                        self._interrupt()
                    if interrupted_at is None and now - started > segment + 20:
                        failure = 'Router capture timed out; cleanup requires verification.'
                        interrupted_at = now
                        self._interrupt()
                    if interrupted_at is not None and now - interrupted_at > 10 and process.poll() is None:
                        process.kill()
                        failure = 'Router did not acknowledge stop; cleanup requires verification.'
                    try:
                        chunk = chunks.get(timeout=.2)
                    except queue.Empty:
                        continue
                    if chunk is None:
                        break
                    if isinstance(chunk, Exception):
                        raise chunk
                    text = chunk.decode('ascii', errors='replace')
                    if not capture_started and 'RUVIEW_CAPTURE_STARTED' in control_tail + text:
                        capture_started = True
                        with CAPTURE_LOCK:
                            if not self.pause_requested and not self.stop_requested.is_set():
                                self.segment_started = time.monotonic()
                    control_tail = (control_tail + text)[-64:]
                    output.append(text)
                    for raw in parser.feed(text):
                        self._append(raw, seq); seq += 1
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait()
                if self.process.stdout is not None:
                    self.process.stdout.close()
                if self.process.stdin is not None:
                    self.process.stdin.close()
                code = self.process.returncode
                self.process = None
                reader.join(timeout=1)
                self._freeze_clock()
                # Keep command diagnostics, not raw CSI hex dumps, in the session log.
                diagnostic = '\n'.join(line for line in ''.join(output).splitlines()
                                       if '0x' not in line and 'CSI record:' not in line)[-4000:]
                if failure:
                    break
                if self.stop_requested.is_set():
                    break
                if self.pause_requested:
                    self._set_status('paused', log='Capture paused; router monitor segment stopped safely.')
                    continue
                if code or seq == segment_records:
                    failure = f'Router capture failed (exit={code}, records={seq-segment_records}). {diagnostic}'
                    break
                if not capture_started or time.monotonic() - started < segment:
                    failure = 'Router capture ended before the requested duration: ' + diagnostic
                    break
                # A successful bounded remote sleep consumed this entire segment.
                # Do not charge SSH/setup time or start a second tiny segment.
                self.remaining = 0
            if failure:
                LOGGER.error('Capture failed session=%s records=%d reason=%s', self.session, seq, failure)
                self._set_status('failed', time.time(), failure)
            elif self.stop_requested.is_set():
                self._set_status('stopped', time.time(), 'Stopped from panel; router cleanup requested.')
            else:
                self._set_status('captured', time.time())
        except Exception as exc:
            failure = str(exc)
            LOGGER.exception('Panel capture failed session=%s', self.session)
            reader_cancel.set()
            self._interrupt()
            if self.process is not None:
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                finally:
                    self.process.stdin.close()
                    self.process.stdout.close()
                    self.process = None
            self._set_status('failed', time.time(), failure)
        finally:
            reader_cancel.set()
            if reader is not None:
                reader.join(timeout=2)
            self._freeze_clock()
            with CAPTURE_LOCK:
                global ACTIVE_CAPTURE
                if ACTIVE_CAPTURE is self:
                    ACTIVE_CAPTURE = None


def capture_snapshot(connection, session, live_after=None):
    value = get_session(connection, session)
    result = {'id': session, 'session': value, 'annotations': annotations(connection, session),
              'paused': value['status'] == 'paused', 'stopping': False,
              'remaining_s': None, 'samples': []}
    with CAPTURE_LOCK:
        job = ACTIVE_CAPTURE
        if job is not None and job.session == session and job.thread.is_alive():
            result.update(paused=job.pause_requested, stopping=job.stop_requested.is_set(),
                          pausing=job.pause_requested and not job.pause_ready,
                          remaining_s=job.remaining_seconds())
    if value['status'] == 'failed':
        result['capture_error'] = connection.execute('SELECT log FROM sessions WHERE id=?', (session,)).fetchone()[0]
    if live_after is not None:
        with CAPTURE_LOCK:
            cached = LATEST_CAPTURE
        if cached is not None and cached.session == session:
            result.update(cached.live_payload(live_after))
        else:
            # Server restart: bounded recovery window, never an unbounded replay.
            rows = connection.execute('SELECT seq,raw FROM records WHERE session=? '
                                      'ORDER BY seq DESC LIMIT 600', (session,)).fetchall()
            try:
                result.update(measurements(list(reversed(rows)), value['metadata'].get('interval_ms', 100)))
            except ValueError as exc:
                result['signal_error'] = str(exc)
            result.update(reset=True, next_seq=rows[0][0] if rows else -1, last_sample_age_s=None)
    elif value['records']:
        try:
            result.update(replay(connection, value))
        except RequestError as exc:
            # Signal errors must not hide the identity or lifecycle controls.
            result['signal_error'] = str(exc)
    return result


def start_capture(body):
    seconds = int(number(body.get('seconds', 60), 'seconds', 5, CAPTURE_MAX_SECONDS))
    interval = int(number(body.get('interval_ms', 100), 'interval_ms', 100, 500))
    if interval not in CAPTURE_INTERVALS:
        raise RequestError('interval_ms must be 100, 200 or 500')
    with CAPTURE_LOCK:
        global ACTIVE_CAPTURE, LATEST_CAPTURE
        if ACTIVE_CAPTURE is not None and ACTIVE_CAPTURE.thread.is_alive():
            raise RequestError('A capture is already active', 409)
        if sum(p.stat().st_size for p in HISTORY.parent.glob('history.sqlite3*')) > 256 * 1024**2:
            raise RequestError('History reached 256 MiB; delete or export sessions before recording', 507)
        sid = str(uuid.uuid4())
        meta = {'router': '192.168.50.1', 'interface': 'eth6',
                'peer': CAPTURE_PEER, 'peer_device': 'RP-AX56 2.4 GHz radio', 'seconds': seconds,
                'interval_ms': interval, 'decoder': PROFILE,
                'clock': 'Pi session wall clock; record timer unit/offset provisional',
                'panel_controlled': True, 'ground_truth': None, 'pose': None}
        with closing(db()) as connection, connection:
            connection.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',
                               (sid, time.time(), None, 'running', json.dumps(meta), ''))
        ACTIVE_CAPTURE = CaptureJob(sid, seconds, interval)
        LATEST_CAPTURE = ACTIVE_CAPTURE
        ACTIVE_CAPTURE.start()
        return sid


def delete_session(connection, sid):
    with CAPTURE_LOCK:
        job = ACTIVE_CAPTURE
        if job is not None and job.session == sid and job.thread.is_alive():
            if not job.pause_requested and not job.stop_requested.is_set():
                raise RequestError('Pause or stop the active capture before deleting its session', 409)
            job.request_stop()
        else:
            job = None
    # Never hold CAPTURE_LOCK while joining: the worker needs it to finish.
    if job is not None:
        job.thread.join(timeout=12)
        if job.thread.is_alive():
            raise RequestError('Capture is still stopping; session retained. Retry deletion shortly.', 409)
    if connection.execute('SELECT 1 FROM sessions WHERE id=?', (sid,)).fetchone() is None:
        raise RequestError('Unknown session', 404)
    connection.execute('DELETE FROM session_annotations WHERE session=?', (sid,))
    connection.execute('DELETE FROM records WHERE session=?', (sid,))
    connection.execute('DELETE FROM sessions WHERE id=?', (sid,))


def active_capture_payload(connection):
    with CAPTURE_LOCK:
        job = ACTIVE_CAPTURE
        if job is None or not job.thread.is_alive():
            return None
        session = get_session(connection, job.session)
        return {'session': session, 'paused': job.pause_requested,
                'pausing': job.pause_requested and not job.pause_ready,
                'remaining_s': job.remaining_seconds()}


def map_payload():
    floorplan = load_json(MAP_DIR / 'floorplan.json')
    devices = load_json(MAP_DIR / 'devices.json')
    if floorplan['glb_sha256'] != devices['map_glb_sha256']:
        raise RuntimeError('Map geometry and device layout have different scan sources')
    return {'floorplan': floorplan, 'devices': devices['devices'], 'sources': {
        'floorplan_sha256': sha256(MAP_DIR / 'floorplan.json'),
        'devices_sha256': sha256(MAP_DIR / 'devices.json'),
        'image': '/maps/home/floorplan-furnished.png'}}


def context_notes(notes, **context):
    return json.dumps({'format': 'ruview-panel-v2', 'notes': notes, 'context': context})


def unpack(row):
    value = dict(row)
    try:
        notes = json.loads(value.get('notes', ''))
    except (ValueError, TypeError):
        notes = None
    if isinstance(notes, dict) and notes.get('format') == 'ruview-panel-v2':
        value['notes'] = notes['notes']
        value['context'] = notes['context']
    else:
        value['context'] = None
    return value


def text_field(body, name, default='', limit=200):
    value = body.get(name, default)
    if not isinstance(value, str) or len(value) > limit:
        raise RequestError(f'{name} must be text, at most {limit} characters')
    return value.strip()


def number(value, name, minimum=0, maximum=1000000):
    if isinstance(value, bool):
        raise RequestError(f'{name} must be a finite number')
    try:
        value = float(value)
    except (ValueError, TypeError) as exc:
        raise RequestError(f'{name} must be a finite number') from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise RequestError(f'{name} must be between {minimum} and {maximum}')
    return value


def item_id(body):
    value = text_field(body, 'id', str(uuid.uuid4()), 80)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise RequestError('Invalid id')
    return value


def validate_point(body):
    lo, hi = map_payload()['floorplan']['bounds_m']
    return (number(body.get('x'), 'x', lo[0], hi[0]),
            number(body.get('y'), 'y', lo[1], hi[1]))


def region(body):
    value = text_field(body, 'region', 'unknown') or 'unknown'
    if value != 'unknown' and value not in {r['id'] for r in map_payload()['floorplan']['rooms']}:
        raise RequestError('Select a known map region')
    return value


def iso(timestamp):
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).isoformat() if timestamp else None


SESSION_SELECT = '''SELECT s.id,s.started,s.finished,s.status,s.metadata,
(SELECT count(*) FROM records r WHERE r.session=s.id) records,
(SELECT count(*) FROM session_annotations a WHERE a.session=s.id) annotation_count FROM sessions s'''


def session_value(row):
    value = dict(row)
    value['metadata'] = json.loads(value['metadata'] or '{}')
    value['started'] = iso(value['started'])
    value['finished'] = iso(value['finished'])
    value['map_at_capture'] = None  # Historical recordings did not snapshot the map.
    return value


def get_session(connection, sid):
    row = connection.execute(SESSION_SELECT + ' WHERE s.id=?', (sid,)).fetchone()
    if row is None:
        raise RequestError('Session not found', 404)
    return session_value(row)


def points(connection):
    return [unpack(row) for row in connection.execute('SELECT * FROM map_points ORDER BY created,id')]


def annotations(connection, sid):
    return [unpack(row) for row in connection.execute(
        'SELECT * FROM session_annotations WHERE session=? ORDER BY start_s,created', (sid,))]


def replay(connection, session):
    rows = connection.execute('SELECT seq,raw FROM records WHERE session=? ORDER BY seq LIMIT ?',
                              (session['id'], MAX_RECORDS + 1)).fetchall()
    if len(rows) > MAX_RECORDS:
        raise RequestError('Session exceeds replay limit of 10000 records', 413)
    interval = session['metadata'].get('interval_ms', 100)
    if interval not in (100, 200, 500):
        raise RequestError('Unsupported capture interval; cannot infer gaps reliably', 422)
    try:
        return measurements(rows, interval)
    except ValueError as exc:
        raise RequestError(str(exc), 422) from exc


def save_point(connection, body):
    x, y = validate_point(body)
    pid = item_id(body)
    label = text_field(body, 'label')
    if not label:
        raise RequestError('Point name is required')
    notes = context_notes(text_field(body, 'notes', limit=2000), map_sources=map_payload()['sources'])
    connection.execute('INSERT INTO map_points VALUES (?,?,?,?,?,?,?,?)',
                       (pid, label, region(body), x, y, number(body.get('height', 0), 'height', 0, 10), notes, time.time()))
    return {'point': pid}


def save_route(connection, body):
    ids = body.get('points')
    if not isinstance(ids, list) or not 2 <= len(ids) <= 64 or any(not isinstance(x, str) for x in ids):
        raise RequestError('Route requires 2 to 64 point ids')
    existing = {p['id']: p for p in points(connection)}
    if any(pid not in existing for pid in ids):
        raise RequestError('Route references an unknown point')
    if len(set(ids)) < 2:
        raise RequestError('Route requires at least two different points')
    label = text_field(body, 'label')
    if not label:
        raise RequestError('Route name is required')
    rid = item_id(body)
    notes = context_notes(text_field(body, 'notes', limit=2000), map_sources=map_payload()['sources'],
                          point_snapshots=[existing[pid] for pid in ids])
    connection.execute('INSERT INTO map_routes VALUES (?,?,?,?,?,?)',
                       (rid, label, region(body), json.dumps(ids), notes, time.time()))
    return {'route': rid}


def save_annotation(connection, sid, body):
    session = get_session(connection, sid)
    summary = replay(connection, session)['summary']
    duration = summary['duration_s']
    if duration is None or duration <= 0:
        raise RequestError('This session has no usable timeline')
    start = number(body.get('start_s'), 'start_s', 0, duration)
    end = number(body.get('end_s'), 'end_s', start, duration)
    if end <= start:
        raise RequestError('End must be after start')
    activity = text_field(body, 'activity')
    if activity not in ACTIVITIES:
        raise RequestError('Unknown activity')
    pid = body.get('point_id') or None
    point = next((p for p in points(connection) if p['id'] == pid), None)
    if pid and point is None:
        raise RequestError('Unknown reference point')
    kind = text_field(body, 'kind', 'observed')
    if kind not in ('observed', 'planned'):
        raise RequestError('Annotation kind must be observed or planned')
    uncertainty = body.get('timing_uncertainty_s')
    if uncertainty is not None:
        uncertainty = number(uncertainty, 'timing_uncertainty_s', 0, 3600)
    aid = str(uuid.uuid4())
    notes = context_notes(text_field(body, 'notes', limit=2000),
                          map_sources=map_payload()['sources'], point_snapshot=point,
                          time_basis='device-relative-provisional', kind=kind,
                          timing_uncertainty_s=uncertainty, author='local user',
                          map_relation='reference selected after capture; capture layout unknown')
    connection.execute('INSERT INTO session_annotations VALUES (?,?,?,?,?,?,?,?,?)',
                       (aid, sid, pid, start, end, activity, 'user', notes, time.time()))
    return {'annotation_id': aid}


class Handler(BaseHTTPRequestHandler):
    server_version = 'RuViewLab/2.0'

    def log_message(self, fmt, *args):
        # Routine reads stay quiet. No request bodies, tokens, raw records or logs.
        LOGGER.debug('http client=%s %s', self.address_string(), fmt % args)

    def respond(self, raw, content_type, status=200, attachment=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if attachment:
            self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(raw)

    def send_json(self, value, status=200, attachment=None):
        self.respond(json.dumps(value, ensure_ascii=False, allow_nan=False).encode(),
                     'application/json; charset=utf-8', status, attachment)

    def read_json(self):
        # Session token blocks cross-site writes; this is a trusted-LAN panel,
        # not user authentication. No new credentials or persistent secrets.
        if not secrets.compare_digest(self.headers.get('X-Panel-Token', ''), WRITE_TOKEN):
            raise RequestError('Refresh the panel before saving', 403)
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            raise RequestError('Cross-origin writes are disabled', 403)
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise RequestError('Expected application/json', 415)
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= MAX_BODY:
            raise RequestError('Invalid request body size', 413)
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise RequestError('Expected a JSON object')
        return value

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, write):
        started = time.monotonic()
        path = urlparse(self.path).path
        try:
            with closing(db()) as connection:
                if write:
                    body = self.read_json()
                    with connection:
                        if path == '/api/points':
                            result = save_point(connection, body)
                        elif path == '/api/routes':
                            result = save_route(connection, body)
                        elif re.fullmatch(r'/api/sessions/[^/]+/annotations', path):
                            result = save_annotation(connection, path.split('/')[3], body)
                        elif path == '/api/captures':
                            sid = start_capture(body)
                            result = {'session': sid}
                        elif re.fullmatch(r'/api/captures/[^/]+/(pause|resume|stop)', path):
                            parts = path.split('/'); sid, action = parts[3], parts[4]
                            with CAPTURE_LOCK:
                                job = ACTIVE_CAPTURE
                            if job is None or job.session != sid or not job.thread.is_alive():
                                raise RequestError('No active capture for this session', 409)
                            changed = {'pause': job.request_pause, 'resume': job.request_resume,
                                       'stop': job.request_stop}[action]()
                            if not changed:
                                raise RequestError(f'Cannot {action} this capture in its current state', 409)
                            result = {'session': sid, 'action': action}
                        elif re.fullmatch(r'/api/sessions/[^/]+/delete', path):
                            delete_session(connection, path.split('/')[3])
                            result = {'deleted': path.split('/')[3]}
                        else:
                            raise RequestError('Not found', 404)
                    LOGGER.info('metadata saved resource=%s result=%s elapsed_ms=%.1f', path, list(result.values())[0], (time.monotonic()-started)*1000)
                    self.send_json(result, 201)
                else:
                    self.get_resource(connection, path)
        except RequestError as exc:
            self.send_json({'error': str(exc)}, exc.status)
        except sqlite3.IntegrityError:
            self.send_json({'error': 'That identifier already exists'}, 409)
        except (ValueError, TypeError, KeyError):
            self.send_json({'error': 'Invalid request or stored metadata'}, 400)
        except (BrokenPipeError, ConnectionResetError):
            LOGGER.debug('Client disconnected resource=%s', path)
        except Exception:
            LOGGER.exception('Request failed resource=%s elapsed_ms=%.1f', path, (time.monotonic()-started)*1000)
            self.send_json({'error': 'Server error. Inspect the panel service journal.'}, 500)

    def get_resource(self, connection, path):
        if path == '/api/health':
            usage = shutil.disk_usage(HISTORY.parent)
            active = active_capture_payload(connection)
            self.send_json({'status': 'ok', 'service': 'ruview-lab-panel', 'api_version': 'v2',
                            'capture_enabled': True, 'write_token': WRITE_TOKEN,
                            'source_state': 'capturing' if active else 'not-monitored',
                            'active_capture': active,
                            'last_valid_sample_age_s': None,
                            'history_bytes': HISTORY.stat().st_size, 'free_bytes': usage.free,
                            'sessions': connection.execute('SELECT count(*) FROM sessions').fetchone()[0],
                            'records': connection.execute('SELECT count(*) FROM records').fetchone()[0],
                            'server_time': iso(time.time())})
        elif path == '/api/map':
            self.send_json(map_payload())
        elif path == '/api/points':
            self.send_json({'points': points(connection)})
        elif path == '/api/routes':
            self.send_json({'routes': [{**unpack(row), 'points': json.loads(row['points'])}
                                      for row in connection.execute('SELECT * FROM map_routes ORDER BY created,id')]})
        elif path == '/api/sessions':
            params = parse_qs(urlparse(self.path).query)
            offset = int(number(params.get('offset', [0])[0], 'offset', 0, 1000000))
            self.send_json({'sessions': [session_value(row) for row in connection.execute(
                SESSION_SELECT + ' ORDER BY s.started DESC LIMIT 100 OFFSET ?', (offset,))],
                'total': connection.execute('SELECT count(*) FROM sessions').fetchone()[0], 'offset': offset})
        elif re.fullmatch(r'/api/captures/[^/]+/live', path):
            sid = path.split('/')[3]
            params = parse_qs(urlparse(self.path).query)
            after = int(number(params.get('after', [-1])[0], 'after', -1, 1000000000))
            self.send_json(capture_snapshot(connection, sid, live_after=after))
        elif re.fullmatch(r'/api/captures/[^/]+', path):
            sid = path.split('/')[3]
            self.send_json(capture_snapshot(connection, sid))
        elif re.fullmatch(r'/api/sessions/[^/]+(?:/(?:measurements|export))?', path):
            parts = path.split('/')
            session = get_session(connection, parts[3])
            result = {'session': session, 'annotations': annotations(connection, parts[3])}
            if path.endswith('/measurements'):
                result.update(replay(connection, session))
            if path.endswith('/export'):
                count = session['records']
                if count > MAX_RECORDS:
                    raise RequestError('Export exceeds 10000 records; use recorder CLI', 413)
                result['records'] = [{'seq': row[0], 'raw_hex': row[1].hex()} for row in connection.execute(
                    'SELECT seq,raw FROM records WHERE session=? ORDER BY seq', (parts[3],))]
                result['map_at_capture'] = None
                result['export_version'] = 2
            self.send_json(result, attachment='ruview-session.json' if path.endswith('/export') else None)
        else:
            files = {'/': STATIC/'index.html', '/index.html': STATIC/'index.html',
                     '/app.css': STATIC/'app.css', '/theme.css': STATIC/'theme.css',
                     '/app.js': STATIC/'app.js',
                     '/api/docs': STATIC/'api-docs.html',
                     '/api-docs.css': STATIC/'api-docs.css',
                     '/api-docs.js': STATIC/'api-docs.js',
                     '/swagger-ui.css': STATIC/'swagger-ui.css',
                     '/swagger-ui-bundle.js': STATIC/'swagger-ui-bundle.js',
                     '/swagger-ui-standalone-preset.js': STATIC/'swagger-ui-standalone-preset.js',
                     '/api/openapi.json': ROOT/'docs/API.openapi.json',
                     '/maps/home/floorplan-furnished.png': MAP_DIR/'floorplan-furnished.png'}
            file = files.get(path)
            if file is None or not file.is_file():
                raise RequestError('Not found', 404)
            self.respond(file.read_bytes(), (mimetypes.guess_type(file.name)[0] or 'application/octet-stream') + ('; charset=utf-8' if file.suffix in ('.html', '.js', '.css') else ''))


def main():
    global HISTORY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--history', type=Path, default=HISTORY)
    args = parser.parse_args()
    HISTORY = args.history.resolve()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    initialize()
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        LOGGER.info('Panel started host=%s port=%s capture_enabled=true manual_bounded=true', args.host, args.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            LOGGER.info('Panel stopped')


if __name__ == '__main__':
    main()
