"""Bounded channel fixtures and an in-process SSH pair; no device access."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import raw_pipeline as raw
from raw_transport import receive_channel, TransportIncomplete


def source():
    result = dict.fromkeys(raw.SOURCE_FIELDS)
    result.update(source_id='synthetic-channel', operation_id='transport-test',
                  configuration={}, kind='netlink-datagram', origin='synthetic')
    return result


class Channel:
    def __init__(self, chunks=(), stderr=(), status=0, eof=True):
        self.chunks = list(chunks)
        self.errors = list(stderr)
        self.status = status
        self.eof_received = eof
        self.closed = False

    def recv_ready(self):
        return bool(self.chunks)

    def recv(self, size):
        data = self.chunks.pop(0)
        self.chunks[:0] = [data[size:]] if len(data) > size else []
        return data[:size]

    def recv_stderr_ready(self):
        return bool(self.errors)

    def recv_stderr(self, size):
        data = self.errors.pop(0)
        self.errors[:0] = [data[size:]] if len(data) > size else []
        return data[:size]

    def exit_status_ready(self):
        return True

    def recv_exit_status(self):
        return self.status


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'capture'
        self.wire = raw.MAGIC + raw.encode_frame(bytes(range(256)) * 8 + bytes(16))

    def rows(self, sql):
        with closing(sqlite3.connect(self.output / 'raw.sqlite3')) as connection:
            return connection.execute(sql).fetchall()

    def check_bytes(self, expected, status):
        self.assertEqual(b''.join(x[0] for x in self.rows('SELECT raw FROM chunks ORDER BY seq')), expected)
        self.assertEqual(self.rows('SELECT status,bytes,sha256 FROM acquisition'),
                         [(status, len(expected), hashlib.sha256(expected).hexdigest())])

    def test_fair_fragmented_receive_keeps_stderr_and_raw_only_replay(self):
        channel = Channel([self.wire[:9], self.wire[9:]], [b'first\n', b'last\n'])
        with patch.object(raw.decoder, 'decode', side_effect=AssertionError('decode during receipt')):
            result = receive_channel(channel, self.output, source())
        self.assertEqual(result['exit_status'], 0)
        self.check_bytes(self.wire, 'received')
        self.assertEqual((self.output / 'stderr.bin').read_bytes(), b'first\nlast\n')
        raw.process(self.output / 'raw.sqlite3', Path(self.temp.name) / 'derived.sqlite3')
        with closing(sqlite3.connect(Path(self.temp.name) / 'derived.sqlite3')) as connection:
            self.assertEqual(connection.execute('SELECT status FROM frames').fetchall(), [('raw-only',)])

    def test_nonzero_and_missing_status_retain_whole_stream_as_failed(self):
        for code in (3, -1):
            with self.subTest(code=code):
                self.output = Path(self.temp.name) / str(code)
                with self.assertRaises(TransportIncomplete):
                    receive_channel(Channel([self.wire], status=code), self.output, source())
                self.check_bytes(self.wire, 'failed')
                events = [json.loads(line) for line in (self.output / 'transport.jsonl').read_text().splitlines()]
                self.assertEqual(events[-1]['exit_status'], code)

    def test_early_zero_exit_without_eof_times_out_preserving_bytes(self):
        with self.assertRaisesRegex(TransportIncomplete, 'deadline'):
            receive_channel(Channel([self.wire], eof=False), self.output, source(), timeout_s=.05)
        self.check_bytes(self.wire, 'failed')

    def test_prefix_is_committed_before_later_receive_disconnects(self):
        channel = Channel([self.wire, b'next'])
        receive = channel.recv

        def disconnect_after_commit(size):
            if channel.chunks == [b'next']:
                self.check_bytes(self.wire, 'running')
                raise ConnectionError('synthetic transport disconnect')
            return receive(size)

        channel.recv = disconnect_after_commit
        with self.assertRaises(ConnectionError):
            receive_channel(channel, self.output, source())
        self.check_bytes(self.wire, 'failed')

    def test_closed_channel_without_status_is_incomplete(self):
        channel = Channel([self.wire])
        channel.closed = True
        channel.exit_status_ready = lambda: False
        with self.assertRaisesRegex(TransportIncomplete, 'missing_exit_status'):
            receive_channel(channel, self.output, source())
        self.check_bytes(self.wire, 'failed')

    def test_stdout_and_stderr_budgets_fail_with_last_read_retained(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            receive_channel(Channel([self.wire]), self.output, source(), max_bytes=8)
        self.check_bytes(self.wire, 'failed')
        self.output = Path(self.temp.name) / 'stderr-limit'
        with self.assertRaisesRegex(TransportIncomplete, 'stderr_budget'):
            receive_channel(Channel(stderr=[b'12345']), self.output, source(), max_stderr_bytes=4)
        self.assertEqual((self.output / 'stderr.bin').read_bytes(), b'12345')
        self.check_bytes(b'', 'failed')

    def test_preflight_rejects_existing_destination_and_invalid_limits(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            receive_channel(Channel(), self.output, source())
        self.assertEqual(list(self.output.iterdir()), [])
        for timeout in (0, float('nan'), float('inf'), True):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                receive_channel(Channel(), self.output, source(), timeout_s=timeout)

    def test_live_stream_origin_survives_replay_without_enabling_decoder(self):
        descriptor = source()
        descriptor['origin'] = 'live-stream'
        receive_channel(Channel([self.wire]), self.output, descriptor)
        raw.process(self.output / 'raw.sqlite3', Path(self.temp.name) / 'derived.sqlite3')
        self.assertEqual(json.loads(self.rows('SELECT source FROM acquisition')[0][0])['origin'], 'live-stream')

    def test_actual_ssh_channel_without_network_listener(self):
        try:
            import paramiko
        except ImportError:
            self.skipTest('Optional desktop Paramiko unavailable')
        left, right = socket.socketpair()
        server = paramiko.Transport(left)
        client = paramiko.Transport(right)
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        self.addCleanup(server.close)
        self.addCleanup(client.close)

        class Server(paramiko.ServerInterface):
            def check_auth_none(self, username):
                return paramiko.AUTH_SUCCESSFUL

            def check_channel_request(self, kind, chanid):
                return paramiko.OPEN_SUCCEEDED

        import threading
        server.add_server_key(paramiko.RSAKey.generate(2048))
        ready = threading.Event()
        server.start_server(event=ready, server=Server())
        client.start_client(timeout=5)
        client.auth_none('synthetic')
        receiver = client.open_session(timeout=5)
        sender = server.accept(5)
        self.assertIsNotNone(sender)
        # Deliberately send status before data to exercise actual SSH buffering.
        sender.send_exit_status(0)
        sender.sendall(self.wire)
        sender.sendall_stderr(b'synthetic diagnostic\n')
        sender.shutdown_write()
        receive_channel(receiver, self.output, source(), timeout_s=5)
        self.check_bytes(self.wire, 'received')
        self.assertEqual((self.output / 'stderr.bin').read_bytes(), b'synthetic diagnostic\n')


if __name__ == '__main__':
    unittest.main()
