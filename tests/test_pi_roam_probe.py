"""Run the guardian against fake commands/time, never the local Wi-Fi stack."""
import contextlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pi_roam_probe as roam


class Output(io.StringIO):
    def fileno(self):return 1


class PiRoamTests(unittest.TestCase):
    def exercise(self, reject=False, changed=False):
        before={'profile':'original','bssid':'A0:36:BC:16:85:B9','boot':'boot'}
        plan={'id':'012345abcdef','before':before,'target':roam.TARGET}
        state=dict(before);calls=[];clock=[0]
        def command(args,**kwargs):
            calls.append(args)
            if args[0]=='nmcli':out=state['profile']
            elif args[-1]=='status':out='bssid='+state['bssid']+'\nwpa_state=COMPLETED'
            else:
                if args[-1]==roam.TARGET and reject:out='FAIL'
                else:
                    state['bssid']=args[-1];out='OK'
                    if changed and args[-1]==roam.TARGET:state['profile']='user-new-profile'
            return SimpleNamespace(returncode=0,stdout=out)
        def sleep(seconds):clock[0]+=seconds
        output=Output()
        fake={'subprocess':SimpleNamespace(run=command),
              'time':SimpleNamespace(time=lambda:clock[0],monotonic=lambda:clock[0],sleep=sleep),
              'signal':SimpleNamespace(SIGTERM=15,SIGINT=2,signal=lambda *args:None),
              'pathlib':SimpleNamespace(Path=lambda path:SimpleNamespace(read_text=lambda:'boot'))}
        with patch.dict(sys.modules,fake),patch('os.fsync'),contextlib.redirect_stdout(output):
            exec(compile(roam.guard(plan),'<guardian-test>','exec'),{})
        return calls,[json.loads(line) for line in output.getvalue().splitlines()],clock[0]

    def test_timed_return_preserves_profile_and_returns_original_bssid(self):
        calls,events,elapsed=self.exercise()
        targets=[c[-1] for c in calls if 'roam' in c]
        self.assertEqual(targets,[roam.TARGET,'A0:36:BC:16:85:B9'])
        self.assertTrue(events[-1]['restored'])
        self.assertGreaterEqual(elapsed,60)
        self.assertFalse(any('modify' in c or 'save_config' in c for c in calls))

    def test_rejected_roam_still_attempts_return(self):
        calls,events,_=self.exercise(reject=True)
        self.assertIn('operation_failed',[e['event'] for e in events])
        self.assertTrue(events[-1]['restored'])

    def test_externally_changed_profile_is_not_overwritten(self):
        calls,events,_=self.exercise(changed=True)
        self.assertEqual([c[-1] for c in calls if 'roam' in c],[roam.TARGET])
        self.assertEqual(events[-1]['event'],'restore_failed')


if __name__=='__main__':unittest.main()
