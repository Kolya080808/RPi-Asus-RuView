"""Read-only replay of saved CSI, independent of legacy motion-event tables."""
import statistics

from decoder import decode
from live_signal import LiveSignal


def measurements(rows, interval_ms=100):
    signal = LiveSignal(interval=float(interval_ms) / 1000, smoothing=1.0)
    samples, intervals = [], []
    invalid = gaps = incomplete = 0
    last_seconds = None
    for seq, raw in rows:
        incomplete += len(raw) != 2048
        try:
            decoded = decode(raw)
        except ValueError:
            invalid += 1
            signal.reset_filter()
            samples.append({'seq': seq, 'seconds': None, 'valid': False})
            continue
        # A reset is not a missing sample: the entire time axis becomes uncertain.
        point = signal.add(raw)
        if last_seconds is not None:
            intervals.append(point['seconds'] - last_seconds)
        last_seconds = point['seconds']
        gaps += int(point['gap'])
        samples.append({**point, 'seq': seq, 'valid': True,
                        'timer_raw': decoded['timer_candidate'],
                        'amplitude': decoded['amplitude'],
                        'rssi_like': decoded['rssi_like']})
    cadence = statistics.median(intervals) if intervals else None
    return {'samples': samples, 'summary': {
        'records': len(samples), 'valid_records': len(samples) - invalid,
        'invalid_records': invalid, 'gap_count': gaps,
        'incomplete_records': incomplete,
        'duration_s': last_seconds, 'median_interval_s': cadence,
        'sample_rate_hz': 1 / cadence if cadence else None,
        'smoothing_seconds': 1, 'threshold': None,
        'time_basis': 'device-relative-provisional',
        'timing_uncertainty_s': None,
        'meaning': 'Radio-scene change; no location, pose or presence inference'}}
