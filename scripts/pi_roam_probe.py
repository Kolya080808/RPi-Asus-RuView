"""One temporary wpa_supplicant roam, with on-Pi timed return and no profile edits."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import stat
import uuid

import deploy_panel as deploy

ROOT = deploy.ROOT
TARGET = 'A0:36:BC:9B:BF:8A'


def identity(client):
    profile = deploy.run(client, 'nmcli -g GENERAL.CON-UUID device show wlan0')
    status = deploy.run(client, 'sudo -n /usr/sbin/wpa_cli -i wlan0 status')
    fields = dict(line.split('=', 1) for line in status.splitlines() if '=' in line)
    if not re.fullmatch('[0-9a-f-]{36}', profile) or fields.get('wpa_state') != 'COMPLETED':
        raise RuntimeError('Pi is not on a known connected profile')
    return dict(profile=profile, bssid=fields['bssid'].upper(),
                boot=deploy.run(client, 'cat /proc/sys/kernel/random/boot_id'))


def guard(plan):
    """Foreground Python owned by nohup; only log file is added on Pi."""
    return '''import subprocess,time,json,os,signal,sys
from pathlib import Path
plan = ''' + repr({k: plan[k] for k in ('id','before','target')}) + '''
stop = False
def signal_stop(signum, frame):
 global stop
 stop = True
signal.signal(signal.SIGTERM, signal_stop)
signal.signal(signal.SIGINT, signal_stop)
def event(kind, **fields):
 print(json.dumps(dict(event=kind,id=plan['id'],utc=time.time(),**fields)),flush=True)
 os.fsync(sys.stdout.fileno())
def command(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=8)
 if p.returncode: raise RuntimeError('command_failed_'+str(p.returncode))
 return p.stdout.strip()
def state():
 p=command(['nmcli','-g','GENERAL.CON-UUID','device','show','wlan0'])
 s=command(['sudo','-n','/usr/sbin/wpa_cli','-i','wlan0','status'])
 f=dict(line.split('=',1) for line in s.splitlines() if '=' in line)
 return dict(profile=p,bssid=f.get('bssid','').upper(),connected=f.get('wpa_state')=='COMPLETED')
def roam(bssid):
 if command(['sudo','-n','/usr/sbin/wpa_cli','-i','wlan0','roam',bssid])!='OK':
  raise RuntimeError('roam_rejected')
event('started',pid=os.getpid(),boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
attempted=False
try:
 initial=state()
 if initial['profile']!=plan['before']['profile'] or initial['bssid']!=plan['before']['bssid']:
  raise RuntimeError('baseline_changed')
 attempted=True
 roam(plan['target'])
 event('roam_requested')
 ready_end=time.monotonic()+8
 while time.monotonic()<ready_end:
  current=state()
  if current['connected'] and current['bssid']==plan['target']: break
  time.sleep(.2)
 else: raise RuntimeError('target_association_not_confirmed')
 event('target_connected',bssid=current['bssid'])
 end=time.monotonic()+60
 while not stop and time.monotonic()<end: time.sleep(.2)
except Exception as exc:
 event('operation_failed',error_type=type(exc).__name__,reason=str(exc))
finally:
 try:
  current=state()
  if current['profile']!=plan['before']['profile']:
   raise RuntimeError('profile_changed_externally')
  if attempted: roam(plan['before']['bssid'])
  end=time.monotonic()+12
  while time.monotonic()<end:
   current=state()
   if current['connected'] and current['bssid']==plan['before']['bssid']: break
   time.sleep(.5)
  restored=current['connected'] and current['profile']==plan['before']['profile'] and current['bssid']==plan['before']['bssid']
  event('finished',restored=restored,**current)
 except Exception as exc:
  event('restore_failed',error_type=type(exc).__name__,reason=str(exc))
'''


def validate(plan):
    if (not re.fullmatch('[0-9a-f]{12}', plan['id']) or plan['target'] != TARGET
            or plan['path'] != '/tmp/ruview-roam-' + plan['id'] + '.jsonl'
            or plan['code_sha256'] != hashlib.sha256(guard(plan).encode()).hexdigest()):
        raise RuntimeError('Unrecognized roam plan')


def read(client, plan):
    with client.open_sftp() as sftp:
        try:
            info = sftp.lstat(plan['path'])
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            raise RuntimeError('Unknown roam log file')
        with sftp.open(plan['path'], 'rb') as f:
            return f.read()


def prepare():
    manifest = deploy.load_manifest()
    if any(p['status'] != 'restored' for p in manifest.get('pi_roam_checks', [])):
        raise RuntimeError('Previous roam plan unresolved')
    ident = uuid.uuid4().hex[:12]
    client = deploy.connect()
    try:
        plan = dict(id=ident,path='/tmp/ruview-roam-'+ident+'.jsonl',target=TARGET,
                    before=identity(client),status='prepared')
        if read(client, plan) is not None:
            raise RuntimeError('Temporary path already exists')
        plan['code_sha256'] = hashlib.sha256(guard(plan).encode()).hexdigest()
        manifest.setdefault('pi_roam_checks', []).append(plan)
        deploy.save_manifest(manifest)
    finally:client.close()
    print('Prepared Pi roam',ident)


def rollback(apply=False):
    manifest=deploy.load_manifest();plan=manifest['pi_roam_checks'][-1];validate(plan)
    client=deploy.connect()
    try:
        current=identity(client)
        if current!=plan['before']: raise RuntimeError('Pi connection/boot not restored yet')
        data=read(client,plan)
        if plan['status'] in {'prepared','restored'}:
            if data is not None:raise RuntimeError('Unexpected existing roam log')
        else:
            if not data:raise RuntimeError('Missing roam evidence')
            events=[json.loads(line) for line in data.splitlines()]
            if (any(e.get('id')!=plan['id'] for e in events) or
                    events[-1].get('event')!='finished' or not events[-1].get('restored')):
                raise RuntimeError('Return not confirmed by guardian')
            pid=events[0]['pid']
            if type(pid) is not int or pid<=1:raise RuntimeError('Invalid guardian PID')
            script=f"import pathlib; p=pathlib.Path('/proc/{pid}/cmdline'); print('owned' if p.exists() and {('ruview-roam-'+plan['id']).encode()!r} in p.read_bytes().split(bytes([0])) else 'absent')"
            if deploy.run(client,'python3 -c '+shlex.quote(script))!='absent':
                raise RuntimeError('Guardian still running')
            local=ROOT/'recordings'/('pi-roam-'+plan['id']+'.jsonl')
            if local.exists() and local.read_bytes()!=data:raise RuntimeError('Local evidence differs')
            if not local.exists():local.write_bytes(data)
            if apply:
                if read(client,plan)!=data:raise RuntimeError('Log changed')
                with client.open_sftp() as sftp:sftp.remove(plan['path'])
                if read(client,plan) is not None:raise RuntimeError('Log removal failed')
        if apply:plan['status']='restored'
        plan['rollback_checked']=True
        deploy.save_manifest(manifest)
    finally:client.close()
    print('Pi roam rollback', 'applied' if apply else 'checked')


def run():
    manifest=deploy.load_manifest();plan=manifest['pi_roam_checks'][-1];validate(plan)
    if plan['status']!='prepared' or not plan.get('rollback_checked'):
        raise RuntimeError('Need checked prepared roam plan')
    client=deploy.connect()
    try:
        if identity(client)!=plan['before'] or read(client,plan) is not None:
            raise RuntimeError('Pi baseline changed')
        plan['status']='running';deploy.save_manifest(manifest)
        command='umask 077; set -C; nohup /usr/bin/python3 -B -c '+shlex.quote(guard(plan))+' '+shlex.quote('ruview-roam-'+plan['id'])+' > '+shlex.quote(plan['path'])+' 2>&1 < /dev/null & echo $!'
        result=deploy.run(client,command,timeout=10)
        if not result.isdigit():raise RuntimeError('Guardian start uncertain; inspect evidence')
        plan['guardian_pid']=int(result);deploy.save_manifest(manifest)
        print('Roam guardian launched; return after at most 60-second trial window')
    finally:client.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    args=parser.parse_args()
    {'prepare':prepare,'run':run}[args.action]()
