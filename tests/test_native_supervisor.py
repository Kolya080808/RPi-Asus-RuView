"""Linux-only supervisor tests against a fake wl; no sockets or radio commands."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('RUVIEW_SUPERVISOR_TEST_BINARY'),
                     'requires test-only Linux supervisor with fake wl')
class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reader = Path('/tmp/ruview-active-' + uuid.uuid4().hex[:12] + '-reader')
        self.addCleanup(self.reader.unlink, missing_ok=True)
        self.log = Path(self.temp.name) / 'commands'
        self.env = dict(os.environ, RUVIEW_TEST_LOG=str(self.log), RUVIEW_TEST_FAIL='')
        self.binary = os.environ['RUVIEW_SUPERVISOR_TEST_BINARY']
        self.write_reader(True)

    def write_reader(self, ready):
        with self.reader.open('w') as f:
            f.write('#!/usr/bin/python3\nimport os,time\n')
            if ready:f.write("os.write(3,b'R');os.close(3)\nos.write(1,b'RUVRAW1\\n')\ntime.sleep(6)\n")
        self.reader.chmod(0o700)

    def commands(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def run_supervisor(self):
        return subprocess.run([self.binary,'--one-active-trial',str(self.reader)],
                              capture_output=True,env=self.env,timeout=15)

    def test_normal_order_and_output_separation(self):
        result=self.run_supervisor()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.commands(),['add','enable','disable','del'])
        self.assertEqual(result.stdout,b'RUVRAW1\n')

    def test_no_ready_means_no_monitor_commands(self):
        self.write_reader(False)
        self.assertNotEqual(self.run_supervisor().returncode,0)
        self.assertEqual(self.commands(),[])

    def test_failed_add_still_deletes_only_selected_peer(self):
        self.env['RUVIEW_TEST_FAIL']='add'
        self.assertNotEqual(self.run_supervisor().returncode,0)
        self.assertEqual(self.commands(),['add','del'])

    def test_failed_enable_still_attempts_disable_and_delete(self):
        self.env['RUVIEW_TEST_FAIL']='enable'
        self.assertNotEqual(self.run_supervisor().returncode,0)
        self.assertEqual(self.commands(),['add','enable','disable','del'])

    def test_hangup_during_capture_runs_cleanup(self):
        import signal
        child=subprocess.Popen([self.binary,'--one-active-trial',str(self.reader)],
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env)
        try:
            end=time.monotonic()+3
            while 'enable' not in self.commands() and time.monotonic()<end:time.sleep(.02)
            self.assertIn('enable',self.commands())
            child.send_signal(signal.SIGHUP)
            out,err=child.communicate(timeout=8)
            self.assertNotEqual(child.returncode,0,err)
            self.assertEqual(self.commands(),['add','enable','disable','del'])
        finally:
            if child.poll() is None:child.kill();child.wait()


if __name__=='__main__':unittest.main()
