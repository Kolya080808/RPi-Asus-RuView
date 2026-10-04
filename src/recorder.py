"""Bounded CSI capture on Raspberry Pi. Standard library only.

python3 recorder.py capture --seconds 20 --interval-ms 100
python3 recorder.py history
python3 recorder.py export SESSION_ID

No background service, web server, camera, pose generation or automatic deletion.
"""
import argparse
import datetime
import json
import pathlib
import shlex
import sqlite3
import subprocess
import time
import uuid

from decoder import decode, text_records, PROFILE
from motion import analyze

ROOT = pathlib.Path(__file__).resolve().parent
PEER = 'A0:36:BC:9B:BF:89'


def database():
    c = sqlite3.connect(ROOT / 'history.sqlite3')
    c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, started REAL, finished REAL, status TEXT, metadata TEXT, log TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS records (session TEXT, seq INTEGER, raw BLOB, decoded TEXT, PRIMARY KEY(session,seq))')
    return c


def capture(seconds, interval, session_id=None, point_id=None):
    # Bound resource use. Rotation/deletion is intentionally not automatic yet.
    if sum(p.stat().st_size for p in ROOT.glob('history.sqlite3*')) > 256 * 1024**2:
        raise RuntimeError('History reached 256 MiB; export/archive it before recording more.')
    script = '''
set -e
[ "$(wl -i eth6 csimon state | sed -n 's/CSI Monitor: Enabled: //p')" = 0 ]
[ -z "$(wl -i eth6 csimon)" ]
[ -z "$(pidof csimond)" ]
cleanup() {
 set +e
 wl -i eth6 csimon disable
 wl -i eth6 csimon del PEER
 if [ -n "$collector_pid" ]; then kill "$collector_pid" 2>/dev/null || :; wait "$collector_pid" 2>/dev/null || :; fi
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
csimond 23 64 &
collector_pid=$!
sleep 1
wl -i eth6 csimon add PEER INTERVAL
wl -i eth6 csimon enable
sleep SECONDS
wl -i eth6 csimon state
'''.replace('PEER', PEER).replace('INTERVAL', str(interval)).replace('SECONDS', str(seconds))
    command = ['ssh', '-tt', '-i', str(ROOT/'router_key'),
               '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'UserKnownHostsFile='+str(ROOT/'router_known_hosts'),
               '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=5',
               '-o', 'ServerAliveCountMax=2', 'admin@192.168.50.1',
               '/bin/sh -c '+shlex.quote(script)]
    session = session_id or str(uuid.uuid4())
    c = database()
    started = time.time()
    meta = {'router':'192.168.50.1','interface':'eth6','peer':PEER,
            'seconds':seconds,'interval_ms':interval,'decoder':PROFILE,
            'clock':'Pi session wall clock; record timer unit/offset provisional',
            'ground_truth':None, 'pose':None, 'point_id':point_id}
    c.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?)',
              (session,started,None,'running',json.dumps(meta),'')); c.commit()
    try:
        proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=seconds+25)
        output = proc.stdout.decode(errors='replace')
        error = proc.stderr.decode(errors='replace')
        count = 0
        for seq, record in enumerate(text_records(output)):
            try:
                decoded = decode(record)
            except ValueError as exc:
                decoded = {'error':str(exc)}
            c.execute('INSERT INTO records VALUES (?,?,?,?)',
                      (session,seq,record,json.dumps(decoded)))
            count += 1
        status = 'captured' if proc.returncode==0 and count else 'failed'
        c.execute('UPDATE sessions SET finished=?,status=?,log=? WHERE id=?',
                  (time.time(),status,output+'\nSTDERR:\n'+error,session)); c.commit()
        if status == 'captured':
            try:
                print(json.dumps(analyze(c,session)))
            except ValueError as exc:
                print(json.dumps({'motion_analysis':'unavailable','reason':str(exc)}))
        print(json.dumps({'session':session,'records':count,'status':status,'ssh_exit':proc.returncode}))
        if status != 'captured':
            raise RuntimeError(error or output[-2000:] or 'No records received')
    except Exception as exc:
        c.execute('UPDATE sessions SET finished=?,status=?,log=log||? WHERE id=?',
                  (time.time(),'failed','\n'+str(exc),session)); c.commit()
        raise
    finally:
        c.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd',required=True)
    cap = sub.add_parser('capture')
    cap.add_argument('--seconds',type=int,choices=range(5,61),default=20)
    cap.add_argument('--interval-ms',type=int,choices=[100,200,500],default=500)
    cap.add_argument('--session-id')
    cap.add_argument('--point-id')
    sub.add_parser('history')
    export = sub.add_parser('export'); export.add_argument('session')
    args = parser.parse_args()
    if args.cmd == 'capture':
        capture(args.seconds,args.interval_ms,args.session_id,args.point_id)
    else:
        c = database()
        if args.cmd == 'history':
            for row in c.execute('SELECT id,started,status,(SELECT count(*) FROM records WHERE session=s.id) FROM sessions s ORDER BY started DESC'):
                print(row[0],datetime.datetime.fromtimestamp(row[1],datetime.timezone.utc).isoformat(),row[2],row[3])
        else:
            for seq, raw, decoded in c.execute('SELECT seq,raw,decoded FROM records WHERE session=? ORDER BY seq',(args.session,)):
                print(json.dumps({'seq':seq,'raw_hex':raw.hex(),'decoded':json.loads(decoded)}))
        c.close()


if __name__ == '__main__':
    main()
