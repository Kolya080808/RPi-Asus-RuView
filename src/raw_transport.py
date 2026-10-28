"""Journal an already-started SSH channel without decoding or device commands.

The caller owns connection setup, dispatch, and verified remote cleanup. Closing
a channel is not proof of remote termination, so this module never claims that.
Only the channel interface is needed; no SSH dependency is installed on Pi here.
"""
from contextlib import ExitStack
import json
import logging
import math
import os
from pathlib import Path
import time

from raw_pipeline import CHUNK_SIZE, ingest, validate_source

LOG = logging.getLogger('ruview.raw_transport')


class TransportIncomplete(RuntimeError):
    """Received evidence is retained, but producer completion is not established."""


def _sync(file, data):
    file.write(data)
    file.flush()
    os.fsync(file.fileno())


class _ChannelStream:
    def __init__(self, channel, stderr, event, timeout_s, max_stderr_bytes):
        self.channel = channel
        self.stderr = stderr
        self.event = event
        self.deadline = time.monotonic() + timeout_s
        self.max_stderr_bytes = max_stderr_bytes
        self.stderr_bytes = 0
        self.exit_status = None

    def read(self, size):
        channel = self.channel
        while True:
            if time.monotonic() >= self.deadline:
                raise TransportIncomplete('receive_deadline')
            # Fair draining prevents a full stderr window from stalling stdout.
            if channel.recv_stderr_ready():
                data = channel.recv_stderr(CHUNK_SIZE)
                _sync(self.stderr, data)
                self.stderr_bytes += len(data)
                if self.stderr_bytes > self.max_stderr_bytes:
                    raise TransportIncomplete('stderr_budget_exceeded_last_read_retained')
            if channel.recv_ready():
                data = channel.recv(size)
                if data:
                    return data
            # Exit status may arrive before the final output. Check EOF first,
            # then recheck both buffers to cover asynchronous packet arrival.
            if channel.closed or channel.eof_received:
                if channel.recv_ready() or channel.recv_stderr_ready():
                    continue
                if channel.exit_status_ready():
                    self.exit_status = channel.recv_exit_status()
                    self.event('producer_exit', exit_status=self.exit_status)
                    if self.exit_status != 0:
                        raise TransportIncomplete('producer_exit_not_zero_or_missing')
                    return b''
                if channel.closed:
                    raise TransportIncomplete('missing_exit_status')
            time.sleep(min(.01, max(0, self.deadline - time.monotonic())))


def receive_channel(channel, directory, source, *, timeout_s=10,
                    max_bytes=64 * 1024**2, max_stderr_bytes=65536):
    """Receive into a new directory containing raw.sqlite3/stderr.bin/transport.jsonl.

    No in-memory whole-stream copy, parsing, retries or remote commands. A zero
    exit plus drained EOF means transport completion only. Time limits bound
    polling, not filesystem stalls or OS scheduling. Caller must close its SSH
    resources and independently verify the source's planned rollback on failure.
    """
    validate_source(source)
    if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
            or timeout_s <= 0):
        raise ValueError('timeout_s must be finite and positive')
    if any(type(n) is not int or n <= 0 for n in (max_bytes, max_stderr_bytes)):
        raise ValueError('Byte limits must be positive integers')
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    started = time.monotonic()
    with ExitStack() as stack:
        stderr = stack.enter_context((directory / 'stderr.bin').open('xb'))
        events = stack.enter_context((directory / 'transport.jsonl').open('xb'))

        def event(name, **fields):
            _sync(events, (json.dumps(dict(event=name, utc_seconds=time.time(),
                elapsed_s=time.monotonic() - started, **fields)) + '\n').encode())

        event('started', operation_id=source['operation_id'], timeout_s=timeout_s,
              max_bytes=max_bytes, max_stderr_bytes=max_stderr_bytes)
        stream = _ChannelStream(channel, stderr, event, timeout_s, max_stderr_bytes)
        try:
            result = ingest(stream, directory / 'raw.sqlite3', source,
                            max_bytes=max_bytes)
            event('received', **result, exit_status=stream.exit_status,
                  stderr_bytes=stream.stderr_bytes)
            LOG.info('operation=%s transport received bytes=%d elapsed=%.3f',
                     source['operation_id'], result['bytes'], time.monotonic() - started)
            return dict(result, exit_status=stream.exit_status,
                        stderr_bytes=stream.stderr_bytes)
        except BaseException as exc:
            LOG.exception('operation=%s transport incomplete', source['operation_id'])
            try:
                event('failed', error_type=type(exc).__name__,
                      exit_status=stream.exit_status, stderr_bytes=stream.stderr_bytes)
            except OSError:
                LOG.exception('Cannot persist transport failure event')
            raise
