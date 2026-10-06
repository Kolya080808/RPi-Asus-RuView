"""Capture lifecycle regressions with real local pipes and a disposable database."""
from contextlib import closing
import json
import io
from pathlib import Path
import struct
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import web_panel as panel


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(panel, 'HISTORY', Path(self.folder.name) / 'history.sqlite3')
        self.db_patch.start()
        panel.initialize()
        with closing(panel.db()) as c, c:
            c.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)', ('fixture', 1, None, 'running', '{}', ''))

    def tearDown(self):
        self.db_patch.stop()
        self.folder.cleanup()

    def run_worker(self, script, seconds=1):
        job = panel.CaptureJob('fixture', seconds, 100)
        # The worker normally accepts >=5 seconds through the HTTP API.
        job.remaining = max(.3, seconds)
        with patch.object(panel, 'router_command', return_value=[sys.executable, '-u', '-c', script]):
            job.start()
            job.thread.join(timeout=6)
            self.assertFalse(job.thread.is_alive())
        with closing(panel.db()) as c:
            result = dict(c.execute('SELECT * FROM sessions WHERE id="fixture"').fetchone())
            result['records'] = c.execute('SELECT count(*) FROM records').fetchone()[0]
        return job, result

    def test_immediate_ssh_failure_is_drained_and_explained(self):
        job, result = self.run_worker("import sys;print('Capture unavailable: peer is not associated');sys.exit(4)")
        self.assertEqual(result['status'], 'failed')
        self.assertIn('not associated', result['log'])
        with closing(panel.db()) as c:
            self.assertIn('not associated', panel.capture_snapshot(c, 'fixture', -1)['capture_error'])

    def test_empty_successful_process_is_not_a_successful_capture(self):
        _, result = self.run_worker('import time;time.sleep(.4)')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('records=0', result['log'])

    def test_last_pipe_data_is_saved_even_when_process_has_exited(self):
        data = bytearray(320)
        struct.pack_into('<II', data, 16, 0x04041004, 100000)
        text = 'CSI record:\n' + ' '.join(f'0x{w:08x}' for w in struct.unpack('<80I', data)) + '\n'
        _, result = self.run_worker("import time;print('RUVIEW_CAPTURE_STARTED');time.sleep(1.1);print(" + repr(text) + ')')
        self.assertEqual(result['status'], 'captured')
        self.assertEqual(result['records'], 1)

    def test_clock_decreases_freezes_and_resumes_without_charging_pause(self):
        job = panel.CaptureJob('fixture', 60, 100)
        with patch.object(panel.time, 'monotonic', return_value=10):
            job.segment_started = 10
            self.assertEqual(job.remaining_seconds(), 60)
        with patch.object(panel.time, 'monotonic', return_value=12.5):
            self.assertEqual(job.remaining_seconds(), 57.5)
            job._freeze_clock()
        with patch.object(panel.time, 'monotonic', return_value=112.5):
            self.assertEqual(job.remaining_seconds(), 57.5)
            job.segment_started = 112.5
        with patch.object(panel.time, 'monotonic', return_value=114):
            self.assertEqual(job.remaining_seconds(), 56)

    def test_receiver_is_main_router_and_checks_precede_mutations(self):
        command = panel.router_command(5, 100)
        self.assertIn('admin@192.168.50.1', command)
        script = panel.router_script(5, 100)
        self.assertLess(script.index('assoclist'), script.index('trap cleanup'))
        self.assertIn('wl -i eth6 csimon add ' + panel.CAPTURE_PEER, script)
        self.assertIn('wl -i eth6 csimon del ' + panel.CAPTURE_PEER, script)

    def test_resume_waits_for_completed_segment_cleanup(self):
        job = panel.CaptureJob('fixture', 60, 100)
        job.thread = Mock()
        job.thread.is_alive.return_value = True
        job.pause_requested = True
        job.process = None  # The former race window: reader/segment not finalized.
        self.assertFalse(job.request_resume())
        job.pause_ready = True
        self.assertTrue(job.request_resume())
        self.assertFalse(job.pause_ready)
        job.stop_requested.set()
        job.pause_ready = True
        self.assertFalse(job.request_resume())

    def test_storage_failure_cancels_full_reader_queue(self):
        process = Mock(stdout=io.BytesIO(b'x' * 3_000_000), stdin=io.BytesIO())
        process.poll.return_value = None
        job = panel.CaptureJob('fixture', 60, 100)
        parser = Mock()
        parser.feed.return_value = [b'fixture']
        def fail(*args):
            time.sleep(.1)  # Let the producer fill its bounded queue.
            raise OSError('Synthetic storage failure')
        with patch.object(panel.subprocess, 'Popen', return_value=process), \
             patch.object(panel, 'LiveParser', return_value=parser), \
             patch.object(job, '_append', side_effect=fail):
            job.start()
            job.thread.join(timeout=3)
        self.assertFalse(job.thread.is_alive())
        self.assertFalse(any(t.name == 'capture-output' and t.is_alive() for t in threading.enumerate()))


if __name__ == '__main__':
    unittest.main()
