"""Conservative motion indicator for the observed ASUS CSI format.

It measures changes in normalized CSI amplitude. It cannot identify a person,
body part, pose, or a vital sign. Requires a still first eight seconds.
"""
import json
import math
import pathlib
import sqlite3
import statistics
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def calculate(records):
    frames = []
    for raw in records:
        if len(raw) < 320 or struct.unpack_from('<I',raw,16)[0] != 0x04041004:
            raise ValueError('Unsupported CSI record profile')
        values = struct.unpack_from('<112h',raw,96)
        amplitude = [math.hypot(i,q) for i,q in zip(values[::2],values[1::2])]
        scale = math.sqrt(sum(x*x for x in amplitude)/56)
        frames.append([x/max(scale,1e-9) for x in amplitude])
    if len(frames) < 80:
        raise ValueError('Need at least eight seconds of 10 Hz CSI data')
    steps = [0.0]
    for before,after in zip(frames,frames[1:]):
        steps.append(math.sqrt(sum((x-y)**2 for x,y in zip(before,after))/56))
    smoothed = []
    for idx in range(len(steps)):
        lo=max(0,idx-5); hi=min(len(steps),idx+5)
        smoothed.append(sum(steps[lo:hi])/(hi-lo))
    baseline=steps[10:80]
    centre=statistics.median(baseline)
    mad=statistics.median(abs(x-centre) for x in baseline)
    threshold=max(0.05,centre+6*mad)
    return steps,smoothed,threshold,centre,mad


def analyze(connection,session):
    rows=list(connection.execute('SELECT seq,raw FROM records WHERE session=? ORDER BY seq',(session,)))
    if not rows:
        raise ValueError('Session not found or empty')
    records=[row[1] for row in rows]
    steps,smoothed,threshold,baseline,mad=calculate(records)
    timers=[struct.unpack_from('<I',raw,20)[0] for raw in records]
    seconds=[0.0]
    for a,b in zip(timers,timers[1:]):
        seconds.append(seconds[-1]+((b-a)&0xffffffff)/1e6)
    connection.execute('CREATE TABLE IF NOT EXISTS motion_samples (session TEXT, seq INTEGER, seconds REAL, step REAL, smooth REAL, active INTEGER, PRIMARY KEY(session,seq))')
    connection.execute('CREATE TABLE IF NOT EXISTS motion_events (session TEXT, start_s REAL, end_s REAL, peak REAL, threshold REAL, PRIMARY KEY(session,start_s))')
    connection.execute('DELETE FROM motion_samples WHERE session=?',(session,))
    connection.execute('DELETE FROM motion_events WHERE session=?',(session,))
    active=[x>threshold for x in smoothed]
    connection.executemany('INSERT INTO motion_samples VALUES (?,?,?,?,?,?)',
                           ((session,seq,t,step,smooth,int(flag)) for seq,(t,step,smooth,flag)
                            in enumerate(zip(seconds,steps,smoothed,active))))
    start=None;events=[]
    for idx,flag in enumerate(active+[False]):
        if flag and start is None:start=idx
        if not flag and start is not None:
            if seconds[idx-1]-seconds[start]>=2:
                event=(session,seconds[start],seconds[idx-1],max(smoothed[start:idx]),threshold)
                connection.execute('INSERT INTO motion_events VALUES (?,?,?,?,?)',event)
                events.append({'start_s':round(event[1],2),'end_s':round(event[2],2),
                               'peak':round(event[3],3)})
            start=None
    connection.commit()
    return {'session':session,'records':len(records),'baseline_median':round(baseline,4),
            'baseline_mad':round(mad,4),'threshold':round(threshold,4),'events':events,
            'meaning':'CSI motion indicator; no body part or pose inference'}


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python3 motion.py SESSION_ID')
    with sqlite3.connect(ROOT/'history.sqlite3') as db:
        print(json.dumps(analyze(db,sys.argv[1])))
