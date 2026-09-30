"""Incremental parsing and causal smoothing for the observed ASUS CSI profile."""
import math
import re
import struct

from decoder import decode


class LiveParser:
    """Emit the useful 320 bytes immediately; the full text log is saved separately."""
    marker = 'CSI record:'

    def __init__(self):
        self.buffer = ''
        self.active = False
        self.emitted = False

    def feed(self, text):
        self.buffer += text
        result = []
        while True:
            if not self.active:
                index = self.buffer.find(self.marker)
                if index < 0:
                    self.buffer = self.buffer[-len(self.marker):]
                    break
                self.buffer = self.buffer[index + len(self.marker):]
                self.active, self.emitted = True, False
            boundary = self.buffer.find(self.marker)
            current = self.buffer if boundary < 0 else self.buffer[:boundary]
            if not self.emitted:
                words = re.findall(r'0x([0-9a-fA-F]{8})\b', current)
                if len(words) >= 80:
                    result.append(b''.join(struct.pack('<I',int(w,16)) for w in words[:80]))
                    self.emitted = True
            if boundary < 0:
                if len(self.buffer) > 100000:
                    raise ValueError('Unexpected CSI record size in text stream')
                break
            self.buffer = self.buffer[boundary + len(self.marker):]
            self.emitted = False
        return result


class LiveSignal:
    def __init__(self, interval=.1, smoothing=1.0):
        self.interval = interval
        self.smoothing = smoothing
        self.timer = None
        self.previous = None
        self.smooth = None
        self.seconds = 0.0

    def reset_filter(self):
        self.previous = None
        self.smooth = None

    def add(self, raw):
        try:
            d = decode(raw)
        except ValueError:
            self.reset_filter()
            raise
        timer = d['timer_candidate']
        dt = None if self.timer is None else ((timer-self.timer)&0xffffffff)/1e6
        if dt is not None and (dt <= 0 or dt > 10):
            self.reset_filter()
            raise ValueError('Device timer repeated or reset; start a new capture')
        gap = dt is not None and dt > self.interval * 1.8
        if gap:
            self.reset_filter()
        self.seconds += dt or 0
        a = d['amplitude']
        power = math.sqrt(sum(x*x for x in a)/len(a))
        unit = [x/max(power,1e-9) for x in a]
        step = None
        if self.previous is not None:
            step = math.sqrt(sum((x-y)**2 for x,y in zip(unit,self.previous))/len(unit))
            alpha = 1-math.exp(-dt/self.smoothing)
            self.smooth = step if self.smooth is None else self.smooth+alpha*(step-self.smooth)
        result = {'seconds':self.seconds,'amplitude_rms':power,'step':step,
                  'smooth':self.smooth,'gap':gap}
        self.previous, self.timer = unit, timer
        return result
