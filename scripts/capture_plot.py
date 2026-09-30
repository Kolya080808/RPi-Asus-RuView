"""Capture on the Pi, export the exact session, and plot CSI motion locally.

Requires local matplotlib; the existing Pi collector needs no changes.
Examples:
    python scripts/capture_plot.py --seconds 60 --open
    python scripts/capture_plot.py --session SESSION_ID --open
    python scripts/capture_plot.py --input recording.jsonl --open
"""
import argparse
from collections import deque
import datetime
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from decoder import decode


def session_id(value):
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError('Session must be a UUID') from exc


def series(rows):
    """Keep invalid records and timer gaps visible instead of implying stillness."""
    points = []
    previous = None
    previous_timer = None
    elapsed = 0.0
    invalid = 0
    deltas = []
    for row in rows:
        try:
            raw = bytes.fromhex(row['raw_hex'])
            decoded = decode(raw)
        except (KeyError, TypeError, ValueError) as exc:
            invalid += 1
            previous = None
            continue
        timer = decoded['timer_candidate']
        delta = None if previous_timer is None else ((timer - previous_timer) & 0xffffffff) / 1e6
        if delta is not None:
            if delta <= 0 or delta > 10:
                raise ValueError('Device timer repeats or jumps unexpectedly; cannot plot a reliable timeline.')
            elapsed += delta
            deltas.append(delta)
        amplitude = decoded['amplitude']
        power = math.sqrt(sum(x*x for x in amplitude) / len(amplitude))
        unit = [x / max(power, 1e-9) for x in amplitude]
        step = None if previous is None else math.sqrt(sum((x-y)**2 for x,y in zip(unit,previous)) / len(unit))
        points.append({'seconds': elapsed, 'amplitude_rms': power, 'step': step,
                       'delta_s': delta, 'seq': row.get('seq')})
        previous, previous_timer = unit, timer
    if len(points) < 2:
        raise ValueError('Need at least two valid CSI records to plot motion.')
    import statistics
    cadence = statistics.median(deltas)
    gap_count = 0
    window = deque()
    total = 0.0
    for point in points:
        gap = point['delta_s'] is not None and point['delta_s'] > cadence * 1.8
        if gap:
            gap_count += 1
            point['step'] = None
        point['gap_before'] = gap
        if point['step'] is None:
            window.clear()
            total = 0.0
        else:
            window.append((point['seconds'],point['step']))
            total += point['step']
        while window and window[0][0] <= point['seconds'] - 1.0:
            total -= window.popleft()[1]
        point['smooth'] = total / len(window) if window else None
    return points, {'records':len(rows), 'valid_records':len(points), 'invalid_records':invalid,
                    'duration_s':points[-1]['seconds'], 'median_interval_s':cadence,
                    'gap_count':gap_count, 'smoothing':'Trailing 1-second mean; reset at gaps or invalid records',
                    'meaning':'Changes in normalized CSI amplitude; not pose or location',
                    'clock':'Provisional device timer, assumed microseconds; relative to first valid record',
                    'ground_truth':None}


def plot(rows, folder, title):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    points,report = series(rows)
    report['session'] = title
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'analysis.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (folder / 'samples.json').write_text(json.dumps(points,indent=2)+'\n',encoding='utf-8')
    # Insert breaks so missing records are not drawn as continuous measurements.
    t,power,step,smooth = [],[],[],[]
    for p in points:
        if p['gap_before']:
            t.append(p['seconds']);power.append(math.nan);step.append(math.nan);smooth.append(math.nan)
        t.append(p['seconds']);power.append(p['amplitude_rms'])
        step.append(p['step'] if p['step'] is not None else math.nan)
        smooth.append(p['smooth'] if p['smooth'] is not None else math.nan)
    fig,(a,b)=plt.subplots(2,1,figsize=(12,6),sharex=True,layout='constrained')
    a.plot(t,power,lw=.8,label='CSI amplitude RMS')
    b.plot(t,step,lw=.7,alpha=.8,label='Change between adjacent normalized CSI frames')
    b.plot(t,smooth,lw=1.6,label='Trailing 1-second mean')
    a.set_ylabel('Amplitude RMS, raw units')
    b.set_ylabel('Normalized CSI step')
    b.set_xlabel('Seconds since first valid CSI record; timer is provisional')
    for ax in (a,b):
        ax.grid(alpha=.2);ax.legend(loc='upper right')
    fig.suptitle(f'CSI motion changes | {title}\n'
                 f"{report['valid_records']} valid records · {report['invalid_records']} invalid · "
                 f"{report['gap_count']} timing gaps · actions not annotated",fontsize=11)
    path=folder/'motion.png'
    fig.savefig(path,dpi=150)
    plt.close(fig)
    return path


def ssh_base(args):
    for p in (args.key,args.known_hosts):
        if not p.is_file():
            raise ValueError(f'Required SSH file not found: {p}')
    if not shutil.which('ssh'):
        raise ValueError('OpenSSH client is not available on PATH.')
    return ['ssh','-i',str(args.key),'-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
            '-o',f'UserKnownHostsFile={args.known_hosts}','-o','ConnectTimeout=8',
            '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',args.host]


def remote(args, command, timeout):
    return subprocess.run(ssh_base(args)+[command],capture_output=True,text=True,
                          encoding='utf-8',errors='replace',timeout=timeout)


def read_rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group()
    source.add_argument('--session',type=session_id,help='Export an existing Pi session without recording')
    source.add_argument('--input',type=Path,help='Plot a saved JSONL export without SSH')
    parser.add_argument('--seconds',type=int,choices=range(5,61),default=60,metavar='5..60')
    parser.add_argument('--interval-ms',type=int,choices=[100,200,500],default=100)
    parser.add_argument('--delay',type=int,default=15,help='Preparation countdown before requesting capture')
    parser.add_argument('--host',default='pi@192.168.50.100')
    parser.add_argument('--key',type=Path,default=Path.home()/'.ssh/ruview_pi_lab')
    parser.add_argument('--known-hosts',type=Path,default=Path.home()/'.ssh/ruview_known_hosts')
    parser.add_argument('--output',type=Path,default=ROOT/'recordings')
    parser.add_argument('--open',action='store_true',help='Open the finished PNG in the default image viewer')
    args=parser.parse_args()
    if not 0 <= args.delay <= 300:parser.error('--delay must be between 0 and 300 seconds')
    # Verify plotting is available before asking the router to collect data.
    try:
        import matplotlib
    except ImportError as exc:
        raise ValueError('Install local plotting support: python -m pip install matplotlib') from exc
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S-%fZ')
    folder=args.output/stamp
    sid=args.session
    capture_log=None
    if args.input:
        text=args.input.read_text(encoding='utf-8-sig')
        title=args.input.stem
    else:
        recorder='python3 /home/pi/ruview-lab/recorder.py'
        if not sid:
            print('Checking Pi access before the countdown...',flush=True)
            check=remote(args,'test -f /home/pi/ruview-lab/recorder.py',15)
            if check.returncode:
                raise ValueError('Pi unavailable or collector missing: '+check.stderr.strip())
            print('Keep still for the first 10 seconds of capture, then move and pause. '
                  'The graph opens after recording; this is not a live display.',flush=True)
            for remaining in range(args.delay,0,-1):
                print(f'Preparation: {remaining:2d} s',end='\r',flush=True)
                time.sleep(1)
            print(f'\nRequesting {args.seconds}-second capture (SSH startup adds a small delay)...',flush=True)
            try:
                result=remote(args,f'{recorder} capture --seconds {args.seconds} --interval-ms {args.interval_ms}',args.seconds+50)
            except subprocess.TimeoutExpired as exc:
                folder.mkdir(parents=True,exist_ok=True)
                output=exc.stdout or b''
                if isinstance(output,bytes):output=output.decode('utf-8',errors='replace')
                (folder/'capture.log').write_text(output,encoding='utf-8')
                raise ValueError(f'SSH timed out. Log saved in {folder}; check Pi history before retrying.') from exc
            capture_log=result.stdout+'\nSTDERR:\n'+result.stderr
            summaries=[]
            for line in result.stdout.splitlines():
                try:item=json.loads(line)
                except ValueError:continue
                if isinstance(item,dict) and 'session' in item and 'status' in item:summaries.append(item)
            if not summaries or result.returncode or summaries[-1]['status']!='captured':
                folder.mkdir(parents=True,exist_ok=True)
                (folder/'capture.log').write_text(capture_log,encoding='utf-8')
                raise ValueError(f'Capture failed. Details: {folder / "capture.log"}')
            sid=session_id(summaries[-1]['session'])
        title=sid
        print(f'Exporting session {sid}...',flush=True)
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'session.json').write_text(json.dumps({'session':sid,'host':args.host},indent=2)+'\n',encoding='utf-8')
        if capture_log is not None:(folder/'capture.log').write_text(capture_log,encoding='utf-8')
        result=remote(args,f'{recorder} export {shlex.quote(sid)}',60)
        if result.returncode:
            raise ValueError(f'Export failed for {sid}; retry with --session {sid}. '+result.stderr.strip())
        text=result.stdout
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'records.jsonl').write_text(text,encoding='utf-8')
    path=plot(read_rows(text),folder,title)
    print(f'Saved PNG: {path.resolve()}\nRaw data and analysis: {folder.resolve()}',flush=True)
    if args.open:
        if os.name=='nt':os.startfile(path.resolve())
        else:print('Open the PNG path above in your image viewer.')


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:
        print('\nInterrupted. A requested remote capture is bounded; check Pi history before retrying.',file=sys.stderr)
        sys.exit(130)
    except (ValueError,OSError,subprocess.TimeoutExpired) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(1)
