"""Bounded SSH output journaling on the PC; never retries a remote command.

Only pass reviewed commands without credentials. Raw output is private evidence,
not application logging. Closing SSH does not prove remote process termination.
"""
from contextlib import ExitStack
import datetime as dt
import json
import logging
import os
from pathlib import Path
import time
import threading
import uuid


LOG = logging.getLogger('ruview.ssh_diagnostics')


class DiagnosticError(RuntimeError):
    """Incomplete command; received bytes remain in the supplied evidence folder."""


def _sync(file, data):
    file.write(data)
    file.flush()
    os.fsync(file.fileno())


def _close_channel(client, channel, remaining):
    """Bound the protocol close wait (including SSH rekey); client is dedicated."""
    done = threading.Event()
    errors = []

    def close():
        try:
            channel.close()
        except Exception as exc:
            errors.append(exc)
        finally:
            done.set()

    closer = threading.Thread(target=close, name='ssh-diagnostic-close', daemon=True)
    closer.start()
    if not done.wait(min(.2, max(0, remaining))) or errors:
        # SSHClient.close/Transport.close closes the socket locally, without
        # waiting to transmit a channel-close packet through a stalled rekey.
        LOG.warning('Closing dedicated diagnostic client after channel-close delay/failure')
        if errors:
            exc = errors[0]
            LOG.error('Diagnostic channel close failed', exc_info=(type(exc), exc, exc.__traceback__))
        client.close()
        closer.join(.2)
        if closer.is_alive():
            LOG.error('Channel-close thread did not stop; client must not be reused')


def collect(client, command, root, *, timeout=10, max_bytes=4 * 1024 * 1024):
    """Return (stdout bytes, stderr bytes, exit status, evidence directory).

    Read the two Channel buffers fairly, without BufferedFile.read(size), and
    sync each chunk before reading more. A nonzero remote status is a complete
    transport result; callers decide whether that command's status is expected.
    Dispatch acknowledgement is bounded too: Paramiko's exec_command timeout
    alone does not bound it. We own the channel before requesting execution and
    close it on deadline. Requires a dedicated client: a stuck protocol close
    shuts down its transport locally. No reconnect or remote cleanup command is
    issued. Byte limits cover stdout and stderr together. These are network-wait
    budgets, not hard real-time bounds on local filesystem I/O or scheduling.
    """
    if timeout <= 0 or max_bytes <= 0:
        raise ValueError('Diagnostic bounds must be positive')
    started = time.monotonic()
    identifier = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:12]
    folder = Path(root) / identifier
    folder.mkdir(parents=True, exist_ok=False)
    channel = None
    dispatcher = None
    counts = {'stdout': 0, 'stderr': 0}
    data = {'stdout': bytearray(), 'stderr': bytearray()}
    metadata = {'id': identifier, 'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'command': command, 'timeout_s': timeout, 'max_bytes': max_bytes}
    with ExitStack() as stack:
        files = {name: stack.enter_context((folder / (name + '.bin')).open('xb'))
                 for name in counts}
        journal = stack.enter_context((folder / 'events.jsonl').open('xb'))

        def event(kind, **fields):
            value = {'event': kind, 'elapsed_s': time.monotonic() - started, **fields}
            _sync(journal, (json.dumps(value) + '\n').encode('utf-8'))

        # If this write fails, no remote command has been submitted.
        event('start', **metadata)
        try:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise DiagnosticError('deadline_before_dispatch')
            channel = client.get_transport().open_session(timeout=remaining)
            channel.settimeout(0)
            dispatch_done = threading.Event()
            dispatch_errors = []

            def dispatch():
                try:
                    channel.exec_command(command)
                except BaseException as exc:
                    dispatch_errors.append(exc)
                finally:
                    dispatch_done.set()

            event('dispatch_requested')
            if time.monotonic() - started >= timeout:
                raise DiagnosticError('deadline_before_dispatch')
            dispatcher = threading.Thread(target=dispatch, name='ssh-diagnostic-dispatch', daemon=True)
            dispatcher.start()
            acknowledged = False
            while True:
                received = False
                for name, ready, receive in (
                        ('stdout', channel.recv_ready, channel.recv),
                        ('stderr', channel.recv_stderr_ready, channel.recv_stderr)):
                    if ready():
                        remaining = max_bytes - sum(counts.values())
                        if remaining <= 0:
                            raise DiagnosticError('output_limit')
                        chunk = receive(min(65536, remaining))
                        if chunk:
                            _sync(files[name], chunk)
                            counts[name] += len(chunk)
                            data[name].extend(chunk)
                            event('received', stream=name, bytes=len(chunk), total=counts[name])
                            received = True
                # Exit status can precede final stdout/stderr packets. Require
                # EOF/close and empty buffers before declaring output complete.
                pending = channel.recv_ready() or channel.recv_stderr_ready()
                if dispatch_done.is_set() and not acknowledged:
                    if dispatch_errors:
                        if not pending:
                            raise DiagnosticError('dispatch_failed') from dispatch_errors[0]
                    else:
                        acknowledged = True
                        event('dispatched')
                if not pending and (channel.closed or channel.eof_received):
                    if acknowledged and channel.exit_status_ready():
                        status = channel.recv_exit_status()
                        if status == -1:
                            raise DiagnosticError('missing_exit_status')
                        event('end', outcome='complete', exit_status=status, counts=counts)
                        LOG.info('diagnostic=%s complete exit=%s bytes=%s elapsed=%.3f',
                                 identifier, status, sum(counts.values()), time.monotonic() - started)
                        return bytes(data['stdout']), bytes(data['stderr']), status, folder
                    if channel.closed and dispatch_done.is_set():
                        raise DiagnosticError('missing_exit_status')
                if time.monotonic() - started >= timeout:
                    raise DiagnosticError('deadline' if acknowledged else 'dispatch_deadline')
                if not received:
                    time.sleep(min(.01, max(0, timeout - (time.monotonic() - started))))
        except BaseException as exc:
            # Keep raw error messages out of operational logs and metadata:
            # they can include remote text. Preserve the original cause below.
            reason = str(exc) if isinstance(exc, DiagnosticError) else type(exc).__name__
            try:
                event('end', outcome='incomplete', reason=reason, counts=counts)
            except OSError:
                LOG.exception('diagnostic=%s could not persist failure marker', identifier)
            LOG.error('diagnostic=%s incomplete reason=%s bytes=%s evidence=%s',
                      identifier, reason, sum(counts.values()), folder)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise DiagnosticError(f'{reason}; partial diagnostics: {folder}') from exc
        finally:
            if channel is not None:
                try:
                    _close_channel(client, channel, timeout - (time.monotonic() - started))
                except Exception:
                    LOG.exception('diagnostic=%s channel close failed; remote state unknown', identifier)
            if dispatcher is not None:
                dispatcher.join(.2)
                if dispatcher.is_alive():
                    LOG.error('diagnostic=%s dispatch thread did not stop; do not reuse client', identifier)
