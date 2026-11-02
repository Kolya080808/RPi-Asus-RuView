"""Read-only replay of saved CSI, independent of legacy motion-event tables."""
import statistics

from decoder import decode
from live_signal import LiveSignal


def measurements(rows, interval_ms=100):
    signal = LiveSignal(interval=float(interval_ms) / 1000, smoothing=1.0)
    samples, intervals = [], []
    invalid = gaps = incomplete = 0
    segment = 0
    discontinuities = []
    last_seconds = None
    for sample_index, (seq, raw) in enumerate(rows):
        incomplete += len(raw) != 2048
        try:
            decoded = decode(raw)
        except ValueError:
            invalid += 1
            signal.reset_filter()
            samples.append({'seq': seq, 'sample_index': sample_index,
                            'seconds': None, 'valid': False})
            continue
        timer = decoded['timer_candidate']
        delta = None if signal.timer is None else ((timer - signal.timer) & 0xffffffff) / 1e6
        discontinuity = delta is not None and (delta <= 0 or delta > 10)
        if discontinuity:
            discontinuities.append({'seq': seq, 'sample_index': sample_index,
                                    'previous_timer_raw': signal.timer,
                                    'timer_raw': timer, 'candidate_delta_s': delta,
                                    'reason': 'unresolved_device_timer_discontinuity'})
            segment += 1
            signal = LiveSignal(interval=float(interval_ms) / 1000, smoothing=1.0)
            last_seconds = None
        point = signal.add(raw)
        if last_seconds is not None:
            intervals.append(point['seconds'] - last_seconds)
        last_seconds = point['seconds']
        gaps += int(point['gap'])
        samples.append({**point, 'seq': seq, 'valid': True,
                        'sample_index': sample_index, 'segment': segment,
                        'segment_seconds': point['seconds'],
                        'discontinuity': discontinuity,
                        'timer_raw': decoded['timer_candidate'],
                        'amplitude': decoded['amplitude'],
                        'rssi_like': decoded['rssi_like']})
    cadence = statistics.median(intervals) if intervals else None
    if discontinuities:
        # Preserve local segment clocks without inventing spacing between them.
        for sample in samples:
            sample['seconds'] = None
    return {'samples': samples, 'discontinuities': discontinuities, 'summary': {
        'records': len(samples), 'valid_records': len(samples) - invalid,
        'invalid_records': invalid, 'gap_count': gaps,
        'incomplete_records': incomplete,
        'duration_s': None if discontinuities else last_seconds, 'median_interval_s': cadence,
        'timeline_continuous': not discontinuities,
        'discontinuity_count': len(discontinuities),
        'segment_count': segment + 1 if len(samples) > invalid else 0,
        'sample_rate_hz': 1 / cadence if cadence else None,
        'smoothing_seconds': 1, 'threshold': None,
        'time_basis': 'device-segment-relative-provisional' if discontinuities else 'device-relative-provisional',
        'timing_uncertainty_s': None,
        'meaning': 'Radio-scene change; no location, pose or presence inference'}}
