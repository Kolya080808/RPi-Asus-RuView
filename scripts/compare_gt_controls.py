"""Reproduce the November 13 comparison of the two September GT sessions.

The saved hand-cued control intervals anchor the exploratory windows. For
held-out scoring use evaluate_gt_points.py, which fixes a label-blind grid.
"""
import argparse
from contextlib import closing
from itertools import product
import json
import logging
import math
from pathlib import Path
import sqlite3
import statistics

from evaluate_gt_points import prototypes, read_session, windows

ROOT = Path(__file__).resolve().parents[1]
POSITION_RANGES = [('near', 3, 12), ('middle', 18, 27), ('far', 33, 57)]


def compare(db):
    position = json.loads((ROOT / 'docs/position-analysis.json').read_text(encoding='utf-8'))
    control = json.loads((ROOT / 'docs/clean-motion-analysis.json').read_text(encoding='utf-8'))
    motion_ranges = [(s['name'], *s['seconds']) for s in control['segments']]
    series = {}
    quality = {}
    links = []
    for report, ranges in [(position, POSITION_RANGES), (control, motion_ranges)]:
        sid = report['session']
        samples, interval, link, _ = read_session(db, sid)
        if len(samples) != report['records']:
            raise ValueError(f'{sid}: unexpected record count for the documented trial')
        links.append((link, interval))
        for name, a, b in ranges:
            group, omitted = windows(samples, interval, start_s=a, end_s=b)
            if not group:
                raise ValueError(f'{sid}: no complete usable window for {name}')
            series[name] = group
            quality[name] = dict(kept=len(group), excluded=omitted,
                                 starts_s=[w.start for w in group])
    if links[0] != links[1]:
        raise ValueError('The two retained trials have different links or capture intervals')

    centers, _, _, radii = prototypes({p: series[p] for p in ('near', 'far')})
    axis = [b - a for a, b in zip(centers['near'], centers['far'])]
    separation = math.hypot(*axis)
    if not separation:
        raise ValueError('The near and far calibration centers coincide')
    comparisons = {}
    means = {tag: tuple(map(statistics.mean, zip(*(w.profile for w in group))))
             for tag, group in series.items()}
    for first, second in [('near', 'far'), ('still_before', 'arms_moving'),
                          ('still_before', 'still_after'), ('arms_moving', 'still_after')]:
        left, right = series[first], series[second]
        d = [math.dist(a.profile, b.profile) for a, b in product(left, right)]
        delta = [b - a for a, b in zip(means[first], means[second])]
        along = sum(x * y for x, y in zip(axis, delta)) / separation
        comparisons[first + '_to_' + second] = dict(
            window_pairs=len(d), min_distance=min(d), median_distance=statistics.median(d),
            max_distance=max(d), centroid_distance=math.hypot(*delta),
            signed_projection_on_near_to_far=along)
    control_distances = []
    for name, _, _ in motion_ranges:
        for w in series[name]:
            d = {p: math.dist(w.profile, v) for p, v in centers.items()}
            nearest = min(d, key=d.get)
            control_distances.append(dict(activity=name, start_s=w.start, distances=d,
                                          inside_nearest_radius=d[nearest] <= radii[nearest]))
    # Select the closest median-step match without looking at profile distance.
    a, b = min(product(series['near'], series['far']),
               key=lambda pair: abs(pair[0].movement - pair[1].movement))
    return dict(position_session=position['session'], control_session=control['session'],
                windows=quality, comparisons=comparisons, calibration_radii=radii,
                control_distances=control_distances, closest_movement_match=dict(
                    near_start_s=a.start, far_start_s=b.start, near_movement=a.movement,
                    far_movement=b.movement, profile_distance=math.dist(a.profile, b.profile)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, required=True)
    args = parser.parse_args()
    try:
        with closing(sqlite3.connect(args.history.resolve().as_uri() + '?mode=ro',
                                     uri=True)) as db:
            db.execute('BEGIN')
            print(json.dumps(compare(db), indent=2))
    except (ValueError, OSError, sqlite3.Error):
        logging.exception('Offline comparison of GT controls failed')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
