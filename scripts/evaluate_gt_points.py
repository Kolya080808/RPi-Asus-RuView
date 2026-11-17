"""Offline two-point baseline for panel exports or a local GT history snapshot.

Train on observed stationary intervals of one session. Predict on a fixed
three-second grid in a different session before reading its reference labels.
"""
import argparse
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
import logging
import math
from pathlib import Path
import sqlite3
import statistics
import sys
from decimal import Decimal, ROUND_CEILING

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from decoder import PROFILE
from panel_signal import measurements
from web_panel import MAX_RECORDS, annotations, timed_record_rows

WIDTH = 3
TICKS_PER_SECOND = 1_000_000
LOG = logging.getLogger('ruview.gt_points')


@dataclass
class Window:
    start: int
    profile: tuple
    movement: float


def read_session(db, sid):
    row = db.execute('SELECT status,metadata FROM sessions WHERE id=?', (sid,)).fetchone()
    if row is None:
        raise ValueError(f'{sid}: session not found')
    if any(col[1] == 'decoded' for col in db.execute('PRAGMA table_info(records)')):
        rows = timed_record_rows(db, sid)
    else:
        rows = db.execute('SELECT seq,raw,NULL FROM records WHERE session=? ORDER BY seq', (sid,))
    return decode_session(sid, row[0], json.loads(row[1]), rows)


def decode_session(sid, status, meta, rows):
    if status not in ('captured', 'stopped'):
        raise ValueError(f'{sid}: need a completed capture')
    if not isinstance(meta, dict) or meta.get('decoder') != PROFILE or meta.get('interface') != 'eth6':
        raise ValueError(f'{sid}: unsupported source metadata')
    interval = meta.get('interval_ms')
    if interval not in (100, 200, 500):
        raise ValueError(f'{sid}: unsupported capture interval')
    rows = list(rows)
    if not rows:
        raise ValueError(f'{sid}: no records')
    link = None
    fingerprints = set()
    for index, (seq, raw, _) in enumerate(rows):
        if type(seq) is not int or seq != index or not isinstance(raw, bytes) or not 320 <= len(raw) <= 2048:
            raise ValueError(f'{sid}: invalid sequence or record length at index {index}')
        if link is None:
            link = raw[4:16]
            if link[:6].hex(':') != str(meta.get('peer')).lower():
                raise ValueError(f'{sid}: configured peer differs from recorded peer')
        elif raw[4:16] != link:
            raise ValueError(f'{sid}: link changed at record {index}')
        # Prefix-only panel exports and full recorder copies compare identically.
        fingerprints.add(hashlib.sha256(raw[:320]).digest())
    replay = measurements(((seq, raw) for seq, raw, _ in rows), interval)
    if not replay['summary']['timeline_continuous'] or replay['summary']['invalid_records']:
        raise ValueError(f'{sid}: unresolved timeline or unsupported record')
    samples = replay['samples']
    previous_read = None
    for sample, (_, _, stamp) in zip(samples, rows):
        if stamp is None:
            continue
        if (type(stamp) is not int or not 0 <= stamp < 2**63 or
                (previous_read is not None and stamp < previous_read)):
            raise ValueError(f'{sid}: invalid Pi read clock at record {sample["seq"]}')
        sample['pi_read_monotonic_ns'] = stamp
        previous_read = stamp
    if any(s['amplitude_rms'] == 0 for s in samples):
        raise ValueError(f'{sid}: zero-power record cannot be normalized')
    return samples, interval, link, fingerprints


def read_export(path):
    """Read the existing /api/sessions/{id}/export v2 file locally."""
    with path.open(encoding='utf-8-sig') as stream:
        data = json.load(stream)
    if (not isinstance(data, dict) or type(data.get('export_version')) is not int or
            data['export_version'] != 2):
        raise ValueError(f'{path.name}: expected panel export version 2')
    header = data.get('session')
    if not isinstance(header, dict) or not isinstance(header.get('id'), str) or not header['id']:
        raise ValueError(f'{path.name}: missing session ID')
    sid = header['id']
    records = data.get('records')
    labels = data.get('annotations')
    if (not isinstance(records, list) or len(records) > MAX_RECORDS or
            type(header.get('records')) is not int or header['records'] != len(records)):
        raise ValueError(f'{sid}: invalid record count in panel export')
    if (not isinstance(labels, list) or type(header.get('annotation_count')) is not int or
            header['annotation_count'] != len(labels) or
            any(not isinstance(a, dict) or a.get('session') != sid for a in labels)):
        raise ValueError(f'{sid}: inconsistent reference annotations in panel export')
    rows = []
    for index, r in enumerate(records):
        if not isinstance(r, dict) or not isinstance(r.get('raw_hex'), str):
            raise ValueError(f'{sid}: missing raw bytes at index {index}')
        if len(r['raw_hex']) % 2 or not 640 <= len(r['raw_hex']) <= 4096:
            raise ValueError(f'{sid}: invalid raw hex length at index {index}')
        try:
            raw = bytes.fromhex(r['raw_hex'])
        except ValueError as exc:
            raise ValueError(f'{sid}: invalid raw hex at index {index}') from exc
        rows.append((r.get('seq'), raw, r.get('pi_read_monotonic_ns')))
    return sid, decode_session(sid, header.get('status'), header.get('metadata'), rows), labels


def read_clock_summary(samples):
    """Variation between elapsed clocks. Absolute transport delay is unknown."""
    stamped = [s for s in samples if 'pi_read_monotonic_ns' in s]
    summary = dict(records=len(samples), timestamped=len(stamped))
    if len(stamped) < 2:
        return summary
    first = stamped[0]
    residuals = [
        (s['pi_read_monotonic_ns'] - first['pi_read_monotonic_ns']) -
        (round(s['seconds'] * TICKS_PER_SECOND) - round(first['seconds'] * TICKS_PER_SECOND)) * 1000
        for s in stamped]
    summary.update(distinct_read_times=len({s['pi_read_monotonic_ns'] for s in stamped}),
                   relative_clock_residual_range_ms=(max(residuals) - min(residuals)) / 1e6)
    return summary


def _window_grid(samples, interval, *, start_s=0, end_s=None):
    """Only complete, covered windows. Drop windows crossed by a cadence gap."""
    # Use integer microseconds to preserve exact boundaries across timer wraps.
    times = [round(s['seconds'] * TICKS_PER_SECOND) for s in samples]
    width = WIDTH * TICKS_PER_SECOND
    origin = start_s * TICKS_PER_SECOND
    end = times[-1] if end_s is None else min(times[-1], end_s * TICKS_PER_SECOND)
    count = max(0, (end - origin) // width)
    groups = [[] for _ in range(count)]
    for t, sample in zip(times, samples):
        slot = (t - origin) // width
        if 0 <= slot < count:
            groups[slot].append((t, sample))
    excluded = {}
    result = []
    tolerance = 1800 * interval  # same 1.8 * nominal interval as LiveSignal
    for i, group in enumerate(groups):
        start = origin + i * width
        if (len(group) < 2 or group[0][0] - start > tolerance or
                start + width - group[-1][0] > tolerance):
            excluded[start_s + WIDTH * i] = 'insufficient_coverage'
            continue
        if any(sample['gap'] for _, sample in group[1:]):
            excluded[start_s + WIDTH * i] = 'internal_gap'
            continue
        profiles = [[v / s['amplitude_rms'] for v in s['amplitude']] for _, s in group]
        profile = tuple(map(statistics.mean, zip(*profiles)))
        movement = statistics.median(s['step'] for _, s in group[1:])
        result.append(Window(start_s + WIDTH * i, profile, movement))
    return result, excluded


def windows(samples, interval, *, start_s=0, end_s=None):
    result, excluded = _window_grid(samples, interval, start_s=start_s, end_s=end_s)
    return result, dict(Counter(excluded.values()))


def observed_intervals(db, sid, duration):
    return reference_intervals(annotations(db, sid), sid, duration)


def reference_intervals(labels, sid, duration):
    """Convert observed bounds to the provisional clock's integer ticks."""
    ranges = []
    points = {}
    for a in labels:
        context = a.get('context')
        if context is None:  # legacy annotation without observed/planned provenance
            continue
        if not isinstance(context, dict):
            raise ValueError(f'{sid}: invalid annotation context')
        if context.get('kind') == 'planned':
            continue
        if context.get('kind') != 'observed':
            raise ValueError(f'{sid}: unknown annotation kind')
        if context.get('time_basis') != 'device-relative-provisional':
            raise ValueError(f'{sid}: reference clock does not match capture clock')
        start, end = a.get('start_s'), a.get('end_s')
        if (type(start) not in (int, float) or type(end) not in (int, float) or
                not 0 <= start < end <= duration + 1e-6):
            raise ValueError(f'{sid}: invalid observed reference interval')
        error = context.get('timing_uncertainty_s')
        if isinstance(error, bool) or not isinstance(error, (int, float)) or not math.isfinite(error) or error < 0:
            raise ValueError(f'{sid}: observed reference requires finite timing uncertainty')
        label = a.get('point_id') if a.get('activity') == 'still' else None
        if label is not None and (not isinstance(label, str) or not label):
            raise ValueError(f'{sid}: invalid stationary reference point ID')
        if label:
            snap = context.get('point_snapshot') or {}
            sources = context.get('map_sources') or {}
            if (not isinstance(snap, dict) or not isinstance(sources, dict) or
                    snap.get('id') != label or not snap.get('region') or
                    any(type(snap.get(k)) not in (int, float) or not math.isfinite(snap[k])
                        for k in ('x', 'y', 'height')) or
                    not sources.get('floorplan_sha256') or not sources.get('devices_sha256')):
                raise ValueError(f'{sid}: missing point geometry for {label}')
            geometry = (snap['region'], snap['x'], snap['y'], snap['height'],
                        sources['floorplan_sha256'], sources['devices_sha256'])
            if label in points and points[label] != geometry:
                raise ValueError(f'{sid}: point geometry changed for {label}')
            points[label] = geometry
        # Panel replay accumulates float seconds. Its duration may be
        # 11.999999999999973 for an exactly 12,000,000-tick recording.
        # Round endpoints to the source resolution; round uncertainty upward.
        ranges.append((round(start * TICKS_PER_SECOND), round(end * TICKS_PER_SECOND),
                       int((Decimal(str(error)) * TICKS_PER_SECOND).to_integral_value(
                           rounding=ROUND_CEILING)), label))
    return ranges, points


def label_for(start, intervals):
    start = start * TICKS_PER_SECOND
    end = start + WIDTH * TICKS_PER_SECOND
    overlaps = [(a, b, err, label) for a, b, err, label in intervals
                if a - err < end and b + err > start]
    if len(overlaps) == 1:
        a, b, err, label = overlaps[0]
        if a + err <= start and end <= b - err:
            return label
    return None


def prototypes(by_point):
    if len(by_point) != 2:
        raise ValueError('Calibration needs covered stationary windows at two distinct points')
    profiles = {p: tuple(map(statistics.mean, zip(*(w.profile for w in group))))
                for p, group in by_point.items()}
    movements = {p: statistics.mean(w.movement for w in group) for p, group in by_point.items()}
    counts = {p: len(group) for p, group in by_point.items()}
    radii = {}
    for p, group in by_point.items():
        if len(group) < 2:
            raise ValueError(f'Calibration needs at least two stationary windows for {p}')
        # Distance to the mean of the *other* windows. Removing one window
        # from the mean scales its residual by n/(n-1).
        radii[p] = max(math.dist(w.profile, profiles[p]) for w in group) * (
            len(group) / (len(group) - 1))
    return profiles, movements, counts, radii


def nearest(distances):
    first, second = sorted(distances, key=distances.get)
    return None if distances[first] == distances[second] else first


def evaluate(db, calibration_id, heldout_id):
    return evaluate_sessions(
        calibration_id, heldout_id, read_session(db, calibration_id), read_session(db, heldout_id),
        lambda: annotations(db, calibration_id), lambda: annotations(db, heldout_id))


def evaluate_exports(calibration_path, heldout_path):
    calibration_id, train, train_labels = read_export(calibration_path)
    heldout_id, test, test_labels = read_export(heldout_path)
    return evaluate_sessions(calibration_id, heldout_id, train, test,
                             lambda: train_labels, lambda: test_labels)


def prepare_calibration(calibration_id, training, labels):
    """Check the first capture independently of any held-out capture."""
    train, interval, _, _ = training
    train_windows, train_excluded = _window_grid(train, interval)
    train_truth, train_points = reference_intervals(labels, calibration_id, train[-1]['seconds'])
    if len(train_points) == 2:
        first, second = train_points.values()
        if first[4:] != second[4:]:
            raise ValueError(f'{calibration_id}: calibration points use different maps or device layouts')
        if first[1:4] == second[1:4]:
            raise ValueError(f'{calibration_id}: calibration points have identical coordinates')
    by_point = {}
    for w in train_windows:
        target = label_for(w.start, train_truth)
        if target is not None:
            by_point.setdefault(target, []).append(w)
    train_reference = reference_coverage(train_windows, train_excluded, train_truth, train_points)
    report = dict(calibration=calibration_id, window_s=WIDTH, status='calibration_ready',
                  calibration_read_clock=read_clock_summary(train),
                  calibration_windows={p: v['usable'] for p, v in train_reference.items()},
                  calibration_reference_coverage=train_reference,
                  calibration_quality_exclusions=dict(Counter(train_excluded.values())))
    if len(train_points) != 2 or any(v['usable'] < 2 for v in train_reference.values()):
        report.update(status='insufficient_reference', stage='calibration', scores=None,
                      reason='Need two observed points with at least two usable windows each')
    return report, by_point, train_points


def evaluate_sessions(calibration_id, heldout_id, training, testing, train_labels, test_labels):
    if calibration_id == heldout_id:
        raise ValueError('Use different calibration and held-out sessions')
    _, interval, link, train_frames = training
    test, test_interval, test_link, test_frames = testing
    if (interval, link) != (test_interval, test_link):
        raise ValueError('Sessions have different radio links or capture intervals')
    if not train_frames.isdisjoint(test_frames):
        raise ValueError('Use independent sessions: calibration and held-out records overlap')
    report, by_point, train_points = prepare_calibration(calibration_id, training, train_labels())
    report['heldout'] = heldout_id
    report['heldout_read_clock'] = read_clock_summary(test)
    if report.get('status') == 'insufficient_reference':
        return report
    test_windows, test_excluded = _window_grid(test, interval)
    profile, movement, counts, radii = prototypes(by_point)
    # The training majority baseline uses stable point ID order to break a tie.
    majority = min(counts, key=lambda p: (-counts[p], p))
    predictions = []
    for w in test_windows:
        distances = {p: math.dist(w.profile, v) for p, v in profile.items()}
        closest = nearest(distances)
        supported = closest if closest is not None and distances[closest] <= radii[closest] else None
        predictions.append(dict(profile=closest, profile_with_radius=supported,
                                movement_only=nearest({p: abs(w.movement - v)
                                                       for p, v in movement.items()}),
                                training_majority=majority))
    truth, test_points = reference_intervals(test_labels(), heldout_id, test[-1]['seconds'])
    if any(p not in train_points or train_points[p] != g for p, g in test_points.items()):
        raise ValueError('Calibration and held-out reference point definitions must match')
    coverage = reference_coverage(test_windows, test_excluded, truth, train_points)
    eligible = {p: v['eligible'] for p, v in coverage.items()}
    scored = sum(v['usable'] for v in coverage.values())
    report.update(calibration_leave_one_window_out_radii=radii,
                  heldout_quality_exclusions=dict(Counter(test_excluded.values())),
                  heldout_reference_coverage=coverage, heldout_reference_windows=eligible,
                  heldout_without_stationary_reference=len(test_windows) - scored,
                  heldout_valid_windows=len(test_windows),
                  heldout_full_windows=len(test_windows) + len(test_excluded), scored=scored)
    if any(v['usable'] == 0 for v in coverage.values()):
        return dict(report, status='insufficient_reference', stage='heldout', scores=None,
                    reason='Need a usable held-out reference window at both points')
    scores = {name: {p: Counter() for p in counts}
              for name in ('profile', 'profile_with_radius', 'movement_only', 'training_majority')}
    for w, votes in zip(test_windows, predictions):
        target = label_for(w.start, truth)
        if target is None:
            continue
        for name, vote in votes.items():
            scores[name][target][vote] += 1
    # Keep abstentions outside the point IDs and in the accuracy denominator.
    summary = {}
    for name, table in scores.items():
        correct = sum(table[p][p] for p in counts)
        abstained = {p: table[p][None] for p in counts}
        reference_count = sum(eligible[p] for p in counts)
        summary[name] = {'confusion': {p: {q: table[p][q] for q in counts} for p in counts},
                         'abstained': abstained, 'correct': correct,
                         'accuracy_on_scored': correct / scored,
                         'correct_fraction_of_reference': correct / reference_count,
                         'decision_coverage_on_reference':
                             (scored - sum(abstained.values())) / reference_count}
    return dict(report, status='scored', scores=summary)


def reference_coverage(usable, excluded, truth, points):
    """Count complete reference windows even where a signal gap prevents a vote."""
    coverage = {p: dict(eligible=0, usable=0, quality_exclusions=Counter()) for p in points}
    for w in usable:
        p = label_for(w.start, truth)
        if p is not None:
            coverage[p]['eligible'] += 1
            coverage[p]['usable'] += 1
    for start, reason in excluded.items():
        p = label_for(start, truth)
        if p is not None:
            coverage[p]['eligible'] += 1
            coverage[p]['quality_exclusions'][reason] += 1
    return coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--history', type=Path)
    source.add_argument('--exports', type=Path, nargs=2, metavar=('CALIBRATION_JSON', 'HELDOUT_JSON'))
    source.add_argument('--check-calibration', type=Path, metavar='CALIBRATION_JSON',
                        help='Check the first panel export before collecting the held-out session')
    parser.add_argument('--calibration', help='Calibration session ID in --history')
    parser.add_argument('--heldout', help='Held-out session ID in --history')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        if args.exports or args.check_calibration:
            if args.calibration or args.heldout:
                parser.error('Panel export inputs supply their own session IDs')
            if args.check_calibration:
                report, _, _ = prepare_calibration(*read_export(args.check_calibration))
            else:
                report = evaluate_exports(*args.exports)
        else:
            if not args.calibration or not args.heldout:
                parser.error('--history requires both --calibration and --heldout')
            with closing(sqlite3.connect(args.history.resolve().as_uri() + '?mode=ro',
                                         uri=True)) as db:
                db.row_factory = sqlite3.Row
                db.execute('BEGIN')
                report = evaluate(db, args.calibration, args.heldout)
        print(json.dumps(report, indent=2))
        if report['status'] == 'insufficient_reference':
            raise SystemExit(3)
    except (ValueError, OSError, sqlite3.Error):
        LOG.exception('Offline GT point evaluation failed')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
