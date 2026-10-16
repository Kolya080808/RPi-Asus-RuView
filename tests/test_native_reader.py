"""Opt-in Linux execution of the native reader's socket-free self-test.

Set RUVIEW_READER_TEST_BINARY to the locally built Linux executable. These
tests never pass a Netlink protocol, enable CSI or contact a device.
"""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import unittest


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('RUVIEW_READER_TEST_BINARY'),
                     'requires local Linux test binary')
class NativeReaderTests(unittest.TestCase):
    def run_reader(self, *args):
        binary = str(Path(os.environ['RUVIEW_READER_TEST_BINARY']).resolve())
        return subprocess.run([binary, *args], capture_output=True, timeout=5, check=False)

    def test_self_test_preserves_complete_bytes_and_error_metadata(self):
        result = self.run_reader('--self-test')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout[:8], b'RUVRAW1\n')
        offset, frames = 8, []
        while offset < len(result.stdout):
            header_len, payload_len = struct.unpack_from('<II', result.stdout, offset)
            offset += 8
            header = json.loads(result.stdout[offset:offset + header_len])
            offset += header_len
            payload = result.stdout[offset:offset + payload_len]
            self.assertEqual(len(payload), payload_len)
            frames.append((header, payload))
            offset += payload_len
        self.assertEqual(offset, len(result.stdout))
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0], ({'source_sequence': 0,
                                    'source_monotonic_ns': 123456789,
                                    'truncated': False, 'receive_error': None},
                                   bytes(i % 256 for i in range(2064))))
        self.assertEqual(frames[1], ({'source_sequence': 1,
                                    'source_monotonic_ns': 123456790,
                                    'truncated': True, 'receive_error': 'MSG_TRUNC'},
                                   bytes(range(17))))

    def test_invalid_arguments_refused_before_output_or_socket(self):
        for args in [(), ('23',), ('24', '1'), ('23', '0'), ('23', '9'),
                     ('23', '-1'), ('23', '01'), ('22', '1extra'),
                     ('--self-test', 'extra')]:
            with self.subTest(args=args):
                result = self.run_reader(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b'')
                self.assertIn(b'usage:', result.stderr)

    def test_closed_stdout_is_failure_not_sigpipe_success(self):
        binary = str(Path(os.environ['RUVIEW_READER_TEST_BINARY']).resolve())
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        try:
            result = subprocess.run([binary, '--self-test'], stdout=write_fd,
                                    stderr=subprocess.PIPE, timeout=5, check=False)
        finally:
            os.close(write_fd)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'stdout frame write', result.stderr)

    def test_stalled_stdout_is_bounded(self):
        binary = str(Path(os.environ['RUVIEW_READER_TEST_BINARY']).resolve())
        read_fd, write_fd = os.pipe()
        os.set_blocking(write_fd, False)
        try:
            while True:
                try:
                    os.write(write_fd, b'x' * 4096)
                except BlockingIOError:
                    break
            started = time.monotonic()
            result = subprocess.run([binary, '--self-test'], stdout=write_fd,
                                    stderr=subprocess.PIPE, timeout=5, check=False)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b'stdout frame write', result.stderr)
        finally:
            os.close(read_fd)
            os.close(write_fd)


if __name__ == '__main__':
    unittest.main()
