"""Open a live ASUS CSI motion window. Start/stop are controlled in the window.

Uses the existing local router key and known-hosts file; no Pi is required.
Requires matplotlib and paramiko. Default capture is bounded to 60 seconds.
"""
import argparse
import datetime
import json
import math
from pathlib import Path
import queue
import shlex
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from live_signal import LiveParser, LiveSignal

PEER='A0:36:BC:9B:BF:89'


def router_script(seconds):
    if not 5 <= seconds <= 600:
        raise ValueError('Capture duration must be 5..600 seconds')
    return '''
set -e
[ "$(wl -i eth6 csimon state | sed -n 's/CSI Monitor: Enabled: //p')" = 0 ]
[ -z "$(wl -i eth6 csimon)" ]
[ -z "$(pidof csimond)" ]
collector_pid=
sleeper_pid=
cleanup() {
 set +e
 if [ -n "$sleeper_pid" ]; then kill "$sleeper_pid" 2>/dev/null; fi
 wl -i eth6 csimon disable
 wl -i eth6 csimon del PEER
 if [ -n "$collector_pid" ]; then kill "$collector_pid" 2>/dev/null; wait "$collector_pid" 2>/dev/null; fi
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM
csimond 23 64 &
collector_pid=$!
sleep 1
wl -i eth6 csimon add PEER 100
wl -i eth6 csimon enable
sleep SECONDS &
sleeper_pid=$!
wait "$sleeper_pid"
wl -i eth6 csimon state
'''.replace('PEER',PEER).replace('SECONDS',str(seconds))


def connect(args):
    import paramiko
    c=paramiko.SSHClient()
    c.load_host_keys(str(args.known_hosts))
    try:
        c.connect(args.host,username='admin',key_filename=str(args.key),
                  look_for_keys=False,allow_agent=False,timeout=5,auth_timeout=5,banner_timeout=5)
        return c
    except BaseException:
        c.close()
        raise


def inspection(c):
    _,out,err=c.exec_command('wl -i eth6 csimon state; wl -i eth6 csimon; pidof csimond || true',timeout=5)
    return out.read().decode(errors='replace')+err.read().decode(errors='replace')


def capture(args,events,stop,folder):
    client=None
    channel=None
    count=0
    error=None
    stopped=False
    try:
        client=connect(args)
        initial=inspection(client)
        (folder/'router-before.txt').write_text(initial,encoding='utf-8')
        # The shell repeats checks immediately before enabling CSI.
        import re
        if not re.search(r'Enabled:\s*0\b',initial):
            raise RuntimeError('Router monitor is already active or its state is unknown')
        if stop.is_set():return
        channel=client.get_transport().open_session(timeout=5)
        channel.get_pty(width=200,height=24)
        channel.exec_command('/bin/sh -c '+shlex.quote(router_script(args.seconds)))
        events.put(('status','Waiting for the first CSI record...'))
        parser=LiveParser()
        deadline=time.monotonic()+args.seconds+20
        with (folder/'router-stream.txt').open('w',encoding='utf-8') as log, (folder/'records.jsonl').open('w',encoding='utf-8') as records:
            while True:
                if stop.is_set():
                    stopped=True
                    channel.send('\x03')
                    channel.close()
                    break
                if time.monotonic()>deadline:
                    raise TimeoutError('Router stream timed out')
                if channel.recv_ready():
                    text=channel.recv(65536).decode('ascii',errors='replace')
                    log.write(text);log.flush()
                    for raw in parser.feed(text):
                        row={'seq':count,'raw_hex':raw.hex(),'received_monotonic':time.monotonic(),
                             'raw_scope':'first 320 payload bytes; full text preserved in router-stream.txt'}
                        records.write(json.dumps(row)+'\n');records.flush()
                        events.put(('record',row))
                        count+=1
                elif channel.exit_status_ready():
                    code=channel.recv_exit_status()
                    if code:raise RuntimeError(f'Router capture exited with status {code}; inspect router-stream.txt')
                    if not count:raise RuntimeError('Capture ended without CSI data')
                    break
                else:
                    time.sleep(.025)
    except Exception as exc:
        error=str(exc)
        events.put(('error',error))
    finally:
        if channel is not None:channel.close()
        cleanup='not verified'
        if client is not None:
            try:
                # Allow the shell HUP/EXIT trap to finish before read-only verification.
                for _ in range(5):
                    time.sleep(.3)
                    final=inspection(client)
                    (folder/'router-after.txt').write_text(final,encoding='utf-8')
                    import re
                    lines=final.splitlines()
                    if re.search(r'Enabled:\s*0\b',final) and not re.search(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}',final) and not any(x.strip().isdigit() for x in lines):
                        cleanup='verified: monitor disabled, peer list empty, no csimond process'
                        break
            except Exception as exc:
                cleanup='not verified: '+str(exc)
            client.close()
        (folder/'capture.json').write_text(json.dumps({'source':'ASUS live CSI','host':args.host,
             'peer':PEER,'interval_ms':100,'requested_seconds':args.seconds,'records':count,
             'stopped_by_user':stopped,'error':error,'cleanup':cleanup},indent=2)+'\n',encoding='utf-8')
        events.put(('done',{'error':error,'cleanup':cleanup,'records':count}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=60,help='Maximum capture duration, 5..600 seconds')
    parser.add_argument('--host',default='192.168.50.1')
    parser.add_argument('--key',type=Path,default=ROOT/'router_key')
    parser.add_argument('--known-hosts',type=Path,default=ROOT/'router_known_hosts')
    parser.add_argument('--output',type=Path,default=ROOT/'recordings')
    args=parser.parse_args()
    router_script(args.seconds)
    import tkinter as tk
    from tkinter import ttk
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.ticker import MultipleLocator,FormatStrFormatter

    win=tk.Tk();win.title('ASUS CSI — Live motion');win.geometry('1150x760')
    controls=ttk.Frame(win,padding=10);controls.pack(fill='x')
    status=tk.StringVar(value='Ready. Press Start, then move and pause to compare the signal.')
    smoothing=tk.DoubleVar(value=1.0)
    figure=Figure(figsize=(11,6),layout='constrained')
    top,bottom=figure.subplots(2,1,sharex=True)
    power_line,=top.plot([],[],color='#2879b9',lw=1,label='Amplitude RMS')
    raw_line,=bottom.plot([],[],color='#9dbdd8',lw=.6,label='Raw change')
    smooth_line,=bottom.plot([],[],color='#ec7c25',lw=2,label='Smoothed change (EMA)')
    top.set_ylabel('Amplitude RMS, raw units');bottom.set_ylabel('Normalized CSI change')
    bottom.yaxis.set_major_locator(MultipleLocator(.1))
    bottom.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
    bottom.set_xlabel('Seconds since first sample · provisional device timer')
    for ax in (top,bottom):ax.grid(alpha=.2);ax.legend(loc='upper right')
    canvas=FigureCanvasTkAgg(figure,master=win)
    events=queue.Queue();stop=threading.Event()
    worker=None;folder=None;signal=None;last=None;closed=False;failure=None
    x=[];power=[];raw=[];smooth=[];samples=[]

    def start():
        nonlocal worker,folder,signal,last,failure
        if worker and worker.is_alive():return
        folder=args.output/('live-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S-%fZ'))
        folder.mkdir(parents=True)
        for values in (x,power,raw,smooth,samples):values.clear()
        signal=LiveSignal(smoothing=smoothing.get());last=None;failure=None;stop.clear()
        while not events.empty():events.get_nowait()
        for line in (power_line,raw_line,smooth_line):line.set_data([],[])
        canvas.draw_idle()
        status.set('Connecting to ASUS...');start_button.config(state='disabled');stop_button.config(state='normal')
        worker=threading.Thread(target=capture,args=(args,events,stop,folder),daemon=True);worker.start()

    def end():
        stop.set();stop_button.config(state='disabled');status.set('Stopping and checking router cleanup...')

    def close():
        nonlocal closed
        closed=True
        if worker and worker.is_alive():end()
        else:win.destroy()

    start_button=ttk.Button(controls,text='Start',command=start);start_button.pack(side='left',padx=4)
    stop_button=ttk.Button(controls,text='Stop',command=end,state='disabled');stop_button.pack(side='left',padx=4)
    ttk.Label(controls,text='Smoothing (seconds):').pack(side='left',padx=(20,6))
    ttk.Scale(controls,from_=.1,to=3,variable=smoothing,length=200).pack(side='left')
    smooth_label=ttk.Label(controls,text='1.0 s');smooth_label.pack(side='left',padx=6)
    ttk.Label(controls,text=f'Capture limit: {args.seconds} s').pack(side='right')
    ttk.Label(win,textvariable=status,padding=10,wraplength=1100).pack(fill='x')
    canvas.get_tk_widget().pack(fill='both',expand=True)

    def poll():
        nonlocal last,failure
        dirty=False
        smooth_label.config(text=f'{smoothing.get():.1f} s')
        if signal:signal.smoothing=smoothing.get()
        for _ in range(1000):
            try:kind,item=events.get_nowait()
            except queue.Empty:break
            if kind=='record':
                try:p=signal.add(bytes.fromhex(item['raw_hex']))
                except ValueError as exc:
                    failure=str(exc);status.set('Invalid data: '+failure);stop.set();continue
                last=time.monotonic()
                if p['gap']:
                    x.append(p['seconds']);power.append(math.nan);raw.append(math.nan);smooth.append(math.nan)
                x.append(p['seconds']);power.append(p['amplitude_rms'])
                raw.append(p['step'] if p['step'] is not None else math.nan)
                smooth.append(p['smooth'] if p['smooth'] is not None else math.nan)
                p['smoothing_seconds']=signal.smoothing;samples.append(p);dirty=True
                status.set(f"LIVE · {len(samples)} samples · {p['seconds']:.1f} s · Changes in the radio scene, not body position")
            elif kind=='status':status.set(item)
            elif kind=='error':failure=item;status.set('ERROR: '+item)
            elif kind=='done':
                if dirty:redraw();dirty=False
                if samples:
                    figure.savefig(folder/'motion.png',dpi=150)
                    (folder/'samples.json').write_text(json.dumps(samples,indent=2)+'\n',encoding='utf-8')
                status.set(('ERROR: '+(failure or item['error']) if failure or item['error'] else 'Finished')+
                           f" · {item['cleanup']} · Saved: {folder}")
                start_button.config(state='normal');stop_button.config(state='disabled')
                last=None
                if closed:win.destroy();return
        if dirty:redraw()
        if last and worker and worker.is_alive() and not stop.is_set() and time.monotonic()-last>2:
            status.set(f'NO NEW DATA for {time.monotonic()-last:.1f} s — the line is frozen, not a stillness reading')
        win.after(100,poll)

    def redraw():
        power_line.set_data(x,power);raw_line.set_data(x,raw);smooth_line.set_data(x,smooth)
        for ax in (top,bottom):ax.relim();ax.autoscale_view()
        bottom.set_xlim(max(0,(x[-1] if x else 0)-60),max(10,x[-1] if x else 10))
        values=[v for v in raw+smooth if math.isfinite(v)]
        # Keep the requested 0.00–0.10 scale when possible, but never clip real peaks.
        upper=max(.1,math.ceil((max(values)*1.08 if values else .1)*10)/10)
        bottom.set_ylim(0,upper)
        canvas.draw_idle()

    win.protocol('WM_DELETE_WINDOW',close)
    win.after(100,poll)
    win.mainloop()


if __name__=='__main__':main()
