"""Paramiko buffers and local SSH socket pairs; no device connections."""
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import paramiko

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ssh_diagnostics as diagnostics
import repeater_probe as probe


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.channel = paramiko.Channel(0)
        self.channel.exec_command = Mock()
        self.client = Mock()
        self.client.get_transport.return_value.open_session.return_value = self.channel

    def finish(self, status=0):
        self.channel.exit_status = status
        self.channel.status_event.set()
        self.channel._handle_eof(None)

    def collect(self, **kwargs):
        return diagnostics.collect(self.client, 'reviewed-read-only-command', self.root, **kwargs)

    def evidence(self):
        folder, = self.root.iterdir()
        events = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
        return folder, events

    def test_short_binary_streams_preserved_on_deadline(self):
        self.channel.in_buffer.feed(b'last stage\x00\xff')
        self.channel.in_stderr_buffer.feed(b'warning without newline')
        with self.assertRaisesRegex(diagnostics.DiagnosticError, 'deadline'):
            self.collect(timeout=.03)
        folder, events = self.evidence()
        self.assertEqual((folder / 'stdout.bin').read_bytes(), b'last stage\x00\xff')
        self.assertEqual((folder / 'stderr.bin').read_bytes(), b'warning without newline')
        self.assertEqual(events[-1]['outcome'], 'incomplete')
        self.channel.exec_command.assert_called_once()

    def test_disconnect_drains_queued_bytes_but_never_reports_success(self):
        self.channel.in_buffer.feed(b'before disconnect')
        self.channel.in_stderr_buffer.feed(b'last stderr')
        with self.channel.lock:
            self.channel._set_closed()
        with self.assertRaisesRegex(diagnostics.DiagnosticError, 'missing_exit_status'):
            self.collect()
        folder, events = self.evidence()
        self.assertEqual((folder / 'stdout.bin').read_bytes(), b'before disconnect')
        self.assertEqual((folder / 'stderr.bin').read_bytes(), b'last stderr')
        self.assertEqual(events[-1]['reason'], 'missing_exit_status')

    def test_large_stderr_and_stdout_are_both_drained_before_exit(self):
        expected = b'e' * 220000
        self.channel.in_buffer.feed(b'normal output')
        self.channel.in_stderr_buffer.feed(expected)
        self.finish(7)
        out, err, status, folder = self.collect()
        self.assertEqual((out, err, status), (b'normal output', expected, 7))
        self.assertEqual((folder / 'stderr.bin').read_bytes(), expected)

    def test_exit_status_before_last_output_waits_for_eof(self):
        self.channel.exit_status = 0
        self.channel.status_event.set()
        def deliver(_):
            self.channel.in_buffer.feed(b'late stdout')
            self.channel.in_stderr_buffer.feed(b'late stderr')
            self.finish()
        with patch.object(diagnostics.time, 'sleep', side_effect=deliver):
            out, err, status, _ = self.collect()
        self.assertEqual((out, err, status), (b'late stdout', b'late stderr', 0))

    def test_eof_without_exit_status_times_out(self):
        self.channel._handle_eof(None)
        with self.assertRaisesRegex(diagnostics.DiagnosticError, 'deadline'):
            self.collect(timeout=.02)

    def test_output_arriving_between_empty_check_and_eof_is_drained(self):
        sync = diagnostics._sync

        def deliver_on_dispatch(file, data):
            sync(file, data)
            if b'"event": "dispatched"' in data:
                self.channel.in_buffer.feed(b'final stdout')
                self.channel.in_stderr_buffer.feed(b'final stderr')
                self.finish()

        with patch.object(diagnostics, '_sync', side_effect=deliver_on_dispatch):
            out, err, status, folder = self.collect()
        self.assertEqual((out, err, status), (b'final stdout', b'final stderr', 0))
        self.assertEqual((folder / 'stdout.bin').read_bytes(), out)
        self.assertEqual((folder / 'stderr.bin').read_bytes(), err)

    def test_output_in_eof_race_still_obeys_byte_limit(self):
        sync = diagnostics._sync

        def deliver_on_dispatch(file, data):
            sync(file, data)
            if b'"event": "dispatched"' in data:
                self.channel.in_buffer.feed(b'0123456789')
                self.finish()

        with patch.object(diagnostics, '_sync', side_effect=deliver_on_dispatch):
            with self.assertRaisesRegex(diagnostics.DiagnosticError, 'output_limit'):
                self.collect(max_bytes=5)
        folder, events = self.evidence()
        self.assertEqual((folder / 'stdout.bin').read_bytes(), b'01234')
        self.assertEqual(events[-1]['outcome'], 'incomplete')

    def test_limit_preserves_exact_prefix_and_marks_incomplete(self):
        self.channel.in_buffer.feed(b'0123456789abcdef')
        self.finish()
        with self.assertRaisesRegex(diagnostics.DiagnosticError, 'output_limit'):
            self.collect(max_bytes=10)
        folder, events = self.evidence()
        self.assertEqual((folder / 'stdout.bin').read_bytes(), b'0123456789')
        self.assertEqual(events[-1]['counts']['stdout'], 10)

    def test_exact_limit_with_complete_exit_is_allowed(self):
        self.channel.in_buffer.feed(b'0123456789')
        self.finish()
        self.assertEqual(self.collect(max_bytes=10)[0], b'0123456789')

    def test_exception_after_partial_read_preserves_cause_and_first_chunk(self):
        self.channel.in_buffer.feed(b'received before error')
        self.channel.in_stderr_buffer.feed(b'unavailable')
        with patch.object(self.channel, 'recv_stderr', side_effect=socket.timeout('synthetic')):
            with self.assertRaises(diagnostics.DiagnosticError) as caught:
                self.collect()
        self.assertIsInstance(caught.exception.__cause__, socket.timeout)
        folder, events = self.evidence()
        self.assertEqual((folder / 'stdout.bin').read_bytes(), b'received before error')
        self.assertEqual(events[-1]['outcome'], 'incomplete')

    def test_disk_failure_prevents_dispatch(self):
        with patch.object(diagnostics.os, 'fsync', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.collect()
        self.client.get_transport.assert_not_called()

    def test_bounded_stdin_sent_once_and_eof_delivered(self):
        self.channel.send = Mock(return_value=len(b'owned test binary'))
        self.channel.shutdown_write = Mock(side_effect=lambda: self.finish())
        self.assertEqual(self.collect(input_bytes=b'owned test binary')[:3], (b'', b'', 0))
        self.channel.send.assert_called_once_with(b'owned test binary')
        self.channel.shutdown_write.assert_called_once()

    def test_oversized_stdin_refused_before_dispatch(self):
        with self.assertRaisesRegex(ValueError, 'stdin'):
            self.collect(input_bytes=b'x' * 65537)
        self.client.get_transport.assert_not_called()

    def test_stdin_partial_window_wait_does_not_duplicate_bytes(self):
        self.channel.send = Mock(side_effect=[3, socket.timeout(), 3])
        self.channel.shutdown_write = Mock(side_effect=lambda: self.finish())
        self.assertEqual(self.collect(input_bytes=b'abcdef')[:3], (b'', b'', 0))
        self.assertEqual([c.args[0] for c in self.channel.send.call_args_list],
                         [b'abcdef', b'def', b'def'])

    def test_real_local_ssh_stdin_larger_than_window(self):
        class Server(paramiko.ServerInterface):
            def check_auth_none(self, username): return paramiko.AUTH_SUCCESSFUL
            def check_channel_request(self, kind, channel_id): return paramiko.OPEN_SUCCEEDED
            def check_channel_exec_request(self, channel, command): return True

        left, right = socket.socketpair()
        server = paramiko.Transport(left, default_window_size=32768)
        transport = paramiko.Transport(right)
        self.addCleanup(server.close)
        self.addCleanup(transport.close)
        server.add_server_key(paramiko.RSAKey.generate(1024))
        expected = bytes(range(256)) * 256
        received = bytearray()
        errors = []

        def serve():
            try:
                server.start_server(server=Server())
                channel = server.accept(3)
                channel.settimeout(3)
                time.sleep(.04)  # Ensure initial receive window fills.
                while True:
                    data = channel.recv(4096)
                    if not data: break
                    received.extend(data)
                channel.sendall(b'stdin complete')
                channel.send_exit_status(0)
                channel.shutdown_write()
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            transport.start_client(timeout=3)
            transport.auth_none('local-test')
            client = paramiko.SSHClient()
            client._transport = transport
            result = diagnostics.collect(client, 'synthetic upload', self.root,
                                         timeout=3, input_bytes=expected)
        finally:
            thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(bytes(received), expected)
        self.assertEqual(result[:3], (b'stdin complete', b'', 0))

    def test_disk_failure_during_receive_is_not_success(self):
        self.channel.in_buffer.feed(b'bytes')
        self.finish()
        with patch.object(diagnostics.os, 'fsync', side_effect=[None, None, OSError('disk full'), None]):
            with self.assertRaisesRegex(diagnostics.DiagnosticError, 'OSError'):
                self.collect()
        _, events = self.evidence()
        self.assertEqual(events[-1]['outcome'], 'incomplete')

    def test_dispatch_exception_is_recorded_without_retry(self):
        self.channel.exec_command.side_effect = EOFError('closed')
        with self.assertRaisesRegex(diagnostics.DiagnosticError, 'dispatch_failed'):
            self.collect()
        _, events = self.evidence()
        self.assertEqual(events[-1]['outcome'], 'incomplete')
        self.channel.exec_command.assert_called_once()

    def test_fast_closed_command_waits_for_dispatch_thread(self):
        def dispatch(_):
            self.channel.in_buffer.feed(b'fast result')
            self.finish()
            self.channel.closed = True
            time.sleep(.03)  # Transport close can beat dispatcher scheduling.
        self.channel.exec_command.side_effect = dispatch
        self.assertEqual(self.collect(timeout=1)[:3], (b'fast result', b'', 0))

    def test_stalled_channel_close_closes_client_without_losing_result(self):
        release = threading.Event()
        self.client.close.side_effect = release.set
        self.channel.close = Mock(side_effect=lambda: release.wait(3))
        self.channel.in_buffer.feed(b'complete result')
        self.finish()
        started = time.monotonic()
        try:
            self.assertEqual(self.collect(timeout=.1)[:3], (b'complete result', b'', 0))
        finally:
            release.set()
        self.assertLess(time.monotonic() - started, 1)
        self.client.close.assert_called_once()
        self.assertFalse(any(t.name == 'ssh-diagnostic-close' for t in threading.enumerate()))

    def test_repeater_run_rejects_nonzero_without_echoing_private_output(self):
        with patch.object(probe, 'collect', return_value=(b'', b'private remote data', 2, self.root)):
            with self.assertRaisesRegex(RuntimeError, 'exited 2') as caught:
                probe.run(self.client, 'read-only')
        self.assertNotIn('private remote data', str(caught.exception))

    def test_remote_file_uses_bounded_collector(self):
        with patch.object(probe, 'collect', return_value=(b'file', b'', 0, self.root)) as collect:
            self.assertEqual(probe.remote_file(self.client, '/tmp/reviewed'), b'file')
            self.assertEqual(collect.call_args.kwargs['max_bytes'], 100000)

    def test_real_local_ssh_disconnect_keeps_both_streams(self):
        self.local_ssh_disconnect(transport_loss=False)

    def test_real_local_ssh_transport_loss_keeps_both_streams(self):
        self.local_ssh_disconnect(transport_loss=True)

    def local_ssh_disconnect(self, transport_loss):
        # Independent of direct Channel buffer fixtures: perform SSH framing,
        # dispatch and disconnect over a socket pair on this PC only.
        class Server(paramiko.ServerInterface):
            def check_auth_none(self, username):
                return paramiko.AUTH_SUCCESSFUL

            def check_channel_request(self, kind, channel_id):
                return paramiko.OPEN_SUCCEEDED

            def check_channel_exec_request(self, channel, command):
                return True

        left, right = socket.socketpair()
        server = paramiko.Transport(left)
        client_transport = paramiko.Transport(right)
        self.addCleanup(server.close)
        self.addCleanup(client_transport.close)
        server.add_server_key(paramiko.RSAKey.generate(1024))
        server_errors = []
        done = threading.Event()

        def serve():
            try:
                server.start_server(server=Server())
                channel = server.accept(3)
                if channel is None:
                    raise AssertionError('No local test channel')
                channel.sendall(b'last diagnostic')
                channel.sendall_stderr(b'last warning')
                # The test closes the channel without an exit-status after
                # dispatch. Buffered bytes must remain usable after close.
                done.wait(3)
                server.close() if transport_loss else channel.close()
            except BaseException as exc:
                server_errors.append(exc)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            client_transport.start_client(timeout=3)
            client_transport.auth_none('local-test')
            client = paramiko.SSHClient()
            client._transport = client_transport
            original = paramiko.Channel.exec_command

            def dispatch(channel, *args, **kwargs):
                result = original(channel, *args, **kwargs)
                done.set()
                return result

            with patch.object(paramiko.Channel, 'exec_command', new=dispatch):
                with self.assertRaisesRegex(diagnostics.DiagnosticError, 'missing_exit_status'):
                    diagnostics.collect(client, 'synthetic', self.root, timeout=3)
        finally:
            done.set()
            thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(server_errors, [])
        folder, _ = self.evidence()
        self.assertEqual((folder / 'stdout.bin').read_bytes(), b'last diagnostic')
        self.assertEqual((folder / 'stderr.bin').read_bytes(), b'last warning')

    def test_real_local_ssh_missing_exec_ack_has_deadline(self):
        release = threading.Event()

        class Server(paramiko.ServerInterface):
            def check_auth_none(self, username):
                return paramiko.AUTH_SUCCESSFUL

            def check_channel_request(self, kind, channel_id):
                return paramiko.OPEN_SUCCEEDED

            def check_channel_exec_request(self, channel, command):
                channel.sendall(b'output before acknowledgement')
                release.wait(3)
                return False

        left, right = socket.socketpair()
        server = paramiko.Transport(left)
        client_transport = paramiko.Transport(right)
        self.addCleanup(server.close)
        self.addCleanup(client_transport.close)
        server.add_server_key(paramiko.RSAKey.generate(1024))
        server.start_server(event=threading.Event(), server=Server())
        client_transport.start_client(timeout=3)
        client_transport.auth_none('local-test')
        client = paramiko.SSHClient()
        client._transport = client_transport
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(diagnostics.DiagnosticError, 'dispatch_deadline'):
                diagnostics.collect(client, 'synthetic', self.root, timeout=.15)
        finally:
            release.set()
        self.assertLess(time.monotonic() - started, 1)
        folder, events = self.evidence()
        self.assertEqual((folder / 'stdout.bin').read_bytes(), b'output before acknowledgement')
        self.assertEqual(events[-1]['reason'], 'dispatch_deadline')
        self.assertFalse(any(t.name == 'ssh-diagnostic-dispatch' for t in threading.enumerate()))


if __name__ == '__main__':
    unittest.main()
