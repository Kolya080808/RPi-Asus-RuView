"""Local synthetic checks for whole-session GT point evaluation."""
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import evaluate_gt_points as gt
from web_panel import context_notes


def frame(tick, point, size=320):
    raw = bytearray(size)
    raw[4:16] = bytes(range(12))
    struct.pack_into('<II', raw, 16, 0x04041004, tick & 0xffffffff)
    for i in range(56):
        high = (i < 28) == (point == 'near')
        struct.pack_into('<hh', raw, 96 + i * 4, 200 if high else 20, 0)
    return bytes(raw)


class PointTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE sessions(id, status, metadata);
            CREATE TABLE records(session, seq INTEGER, raw BLOB);
            CREATE TABLE session_annotations(session,point_id,start_s,end_s,activity,notes,created);
        ''')

    def session(self, sid, first, interval=100, size=320):
        peer = bytes(range(6)).hex(':')
        meta = dict(decoder=gt.PROFILE, interface='eth6', interval_ms=interval, peer=peer)
        self.db.execute('INSERT INTO sessions VALUES(?,?,?)',
                        (sid, 'captured', json.dumps(meta)))
        for seq, ms in enumerate(range(0, 12001, interval)):
            point = first if ms < 6000 else ('far' if first == 'near' else 'near')
            tick = 2**32 - 12345 + ms * 1000 + (1234 if sid == 'test' else 0)
            raw = frame(tick, point, size)
            self.db.execute('INSERT INTO records VALUES(?,?,?)', (sid, seq, raw))
        for point in ('near', 'far'):
            self.annotation(sid, point, 0 if point == first else 6,
                            6 if point == first else 12)

    def annotation(self, sid, point, start, end, kind='observed', error=0, activity='still'):
        notes = context_notes('', kind=kind, timing_uncertainty_s=error,
                              time_basis='device-relative-provisional',
                              map_sources={'floorplan_sha256': 'map', 'devices_sha256': 'layout'},
                              point_snapshot=dict(id=point, region='R', x=int(point == 'near'),
                                                  y=0, height=0))
        self.db.execute('INSERT INTO session_annotations VALUES(?,?,?,?,?,?,?)',
                        (sid, point, start, end, activity, notes, 0))

    def test_reversed_order_real_schema_prefix_full_and_wrap(self):
        self.session('cal', 'near', size=2048)
        self.session('test', 'far')
        self.annotation('test', 'far', 0, 12, kind='planned')
        r = gt.evaluate(self.db, 'cal', 'test')
        self.assertEqual(r['heldout_full_windows'], 4)
        self.assertEqual(r['heldout_reference_windows'], {'near': 2, 'far': 2})
        self.assertEqual(r['scores']['profile']['correct'], 4)
        self.assertEqual(r['scores']['movement_only']['abstained'], {'near': 2, 'far': 2})
        self.assertEqual(r['scores']['profile_with_radius']['correct'], 4)
        self.assertEqual(r['scores']['training_majority']['correct'], 2)
        # Change only reference activities. Features and predictions must stay
        # intact; this conflicting observed interval removes one scoring slot.
        self.annotation('test', None, .5, 1.5, activity='walking')
        changed = gt.evaluate(self.db, 'cal', 'test')
        self.assertEqual(changed['scored'], 3)
        self.assertEqual(changed['scores']['profile']['correct'], 3)
        self.assertEqual(changed['heldout_valid_windows'], 4)

    def test_relabeling_heldout_does_not_feed_predictor(self):
        self.session('cal', 'near')
        self.session('test', 'far')
        self.db.execute("UPDATE session_annotations SET start_s=6-start_s, end_s=18-end_s "
                        "WHERE session='test'")
        r = gt.evaluate(self.db, 'cal', 'test')
        self.assertEqual(r['scores']['profile']['correct'], 0)
        self.assertEqual(r['scored'], 4)

    def test_repeated_capture_under_another_id_rejected(self):
        self.session('cal', 'near', size=2048)
        self.session('copy', 'near', size=320)
        with self.assertRaisesRegex(ValueError, 'independent'):
            gt.evaluate(self.db, 'cal', 'copy')
        with self.assertRaisesRegex(ValueError, 'different'):
            gt.evaluate(self.db, 'cal', 'cal')

    def test_partial_overlap_rejected_even_with_different_lengths(self):
        self.session('cal', 'near', size=2048)
        self.session('test', 'far')
        self.db.execute("UPDATE records SET raw=(SELECT substr(raw,1,320) FROM records "
                        "WHERE session='cal' AND seq=10) WHERE session='test' AND seq=10")
        with self.assertRaisesRegex(ValueError, 'records overlap'):
            gt.evaluate(self.db, 'cal', 'test')

    def test_sequence_and_profile_faults(self):
        self.session('cal', 'near')
        self.db.execute("UPDATE records SET raw=? WHERE seq=2", (bytes(2048),))
        with self.assertRaisesRegex(ValueError, 'link changed'):
            gt.read_session(self.db, 'cal')
        self.db.execute('DELETE FROM records WHERE seq=2')
        with self.assertRaisesRegex(ValueError, 'sequence'):
            gt.read_session(self.db, 'cal')

    def test_clock_discontinuity_and_unknown_reference_uncertainty(self):
        self.session('cal', 'near')
        self.annotation('cal', 'far', 0, 1, error=None)
        with self.assertRaisesRegex(ValueError, 'uncertainty'):
            gt.observed_intervals(self.db, 'cal', 12)
        self.db.execute('UPDATE records SET raw=(SELECT raw FROM records WHERE seq=1) WHERE seq=2')
        with self.assertRaisesRegex(ValueError, 'timeline'):
            gt.read_session(self.db, 'cal')

    def test_edges_and_uncertain_overlap(self):
        self.assertEqual(gt.label_for(3, [(2500000, 6500000, 500000, 'near')]), 'near')
        self.assertIsNone(gt.label_for(3, [(2500000, 6500000, 500001, 'near')]))
        intervals = [(2500000, 6500000, 500000, 'near'), (6100000, 8000000, 200000, None)]
        self.assertIsNone(gt.label_for(3, intervals))

    def test_panel_duration_roundoff_at_exact_end_and_subtick_uncertainty(self):
        self.session('cal', 'near')
        samples, *_ = gt.read_session(self.db, 'cal')
        panel_duration = samples[-1]['seconds']
        self.assertEqual(panel_duration, 12)
        # Older panel snapshots may contain this endpoint even after the
        # replay clock itself has been corrected.
        legacy_duration = 11.999999999999973
        self.assertLess(legacy_duration, panel_duration)
        self.db.execute('UPDATE session_annotations SET end_s=? WHERE point_id=?',
                        (legacy_duration, 'far'))
        bounds, _ = gt.observed_intervals(self.db, 'cal', panel_duration)
        self.assertEqual(gt.label_for(9, bounds), 'far')
        self.db.execute("UPDATE session_annotations SET notes=replace(notes,?,?) WHERE point_id=?",
                        ('"timing_uncertainty_s": 0', '"timing_uncertainty_s": 0.0000001', 'far'))
        bounds, _ = gt.observed_intervals(self.db, 'cal', panel_duration)
        self.assertIsNone(gt.label_for(9, bounds))

    def test_supported_intervals_and_zero_power(self):
        for interval in (100, 200, 500):
            with self.subTest(interval=interval):
                sid = str(interval)
                self.session(sid, 'near', interval)
                samples, dt, _, _ = gt.read_session(self.db, sid)
                w, omitted = gt.windows(samples, dt)
                self.assertEqual([x.start for x in w], [0, 3, 6, 9])
                self.assertEqual(omitted, {})
        raw = bytearray(frame(2**32-12345, 'near'))
        raw[96:320] = bytes(224)
        self.db.execute("UPDATE records SET raw=? WHERE session='100' AND seq=0", (raw,))
        with self.assertRaisesRegex(ValueError, 'zero-power'):
            gt.read_session(self.db, '100')

    def test_control_grid_origin_and_missing_edge(self):
        self.session('control', 'near')
        samples, dt, _, _ = gt.read_session(self.db, 'control')
        # A gap ending at t=4 falls outside the next [4,7) window.
        kept = [s for s in samples if not 3.7 < round(s['seconds'], 3) < 4]
        kept = [dict(s, gap=True) if round(s['seconds'], 3) == 4 else s for s in kept]
        w, omitted = gt.windows(kept, dt, start_s=1, end_s=8)
        self.assertEqual([x.start for x in w], [4])
        self.assertEqual(omitted, {'insufficient_coverage': 1})

    def test_cadence_gap_counts_missing_reference_window(self):
        self.session('cal', 'near')
        self.session('test', 'far')
        self.db.execute("DELETE FROM records WHERE session='test' AND seq=38")
        self.db.execute("UPDATE records SET seq=seq-1 WHERE session='test' AND seq>38")
        r = gt.evaluate(self.db, 'cal', 'test')
        self.assertEqual(r['heldout_quality_exclusions'], {'internal_gap': 1})
        self.assertEqual(sum(r['heldout_reference_windows'].values()), 4)
        self.assertEqual(r['scored'], 3)
        self.assertEqual(r['scores']['profile']['decision_coverage_on_reference'], .75)

    def test_distant_profile_abstains(self):
        self.session('cal', 'near')
        self.session('test', 'far')
        for seq in range(30):
            raw = bytearray(frame(2**32 - 12345 + seq * 100000 + 1234, 'far'))
            raw[96:320] = struct.pack('<hh', 111, 0) * 56
            self.db.execute("UPDATE records SET raw=? WHERE session='test' AND seq=?", (raw, seq))
        r = gt.evaluate(self.db, 'cal', 'test')
        guarded = r['scores']['profile_with_radius']
        self.assertEqual(guarded['abstained']['far'], 1)
        self.assertEqual(guarded['correct_fraction_of_reference'], .75)

    def test_heldout_geometry_changed(self):
        self.session('cal', 'near')
        self.session('test', 'far')
        self.db.execute("UPDATE session_annotations SET notes=replace(notes, ?, ?) "
                        "WHERE session='test'", ('"x": 1', '"x": 2'))
        with self.assertRaisesRegex(ValueError, 'definitions must match'):
            gt.evaluate(self.db, 'cal', 'test')

    def test_short_reference_and_complete_signal_loss_have_different_reports(self):
        self.session('cal', 'near')
        self.session('test', 'far')
        self.db.execute("UPDATE session_annotations SET start_s=.7,end_s=4.8 "
                        "WHERE session='test' AND point_id='far'")
        short = gt.evaluate(self.db, 'cal', 'test')
        self.assertEqual(short['status'], 'insufficient_reference')
        self.assertEqual(short['stage'], 'heldout')
        self.assertIsNone(short['scores'])
        self.assertEqual(short['heldout_reference_coverage']['far'],
                         dict(eligible=0, usable=0, quality_exclusions={}))
        self.db.execute("UPDATE session_annotations SET start_s=0,end_s=6 "
                        "WHERE session='test' AND point_id='far'")
        self.db.execute("DELETE FROM records WHERE session='test' AND seq IN (10,40)")
        self.db.execute("UPDATE records SET seq=seq-(seq>10)-(seq>40) WHERE session='test'")
        gaps = gt.evaluate(self.db, 'cal', 'test')
        self.assertIsNone(gaps['scores'])
        self.assertEqual(gaps['heldout_reference_coverage']['far'],
                         dict(eligible=2, usable=0, quality_exclusions={'internal_gap': 2}))
        self.assertEqual(gaps['heldout_reference_coverage']['near']['usable'], 2)

    def test_calibration_plans_do_not_supply_reference(self):
        self.session('cal', 'near')
        self.session('test', 'far')
        self.db.execute("UPDATE session_annotations SET notes=replace(notes,'observed','planned') "
                        "WHERE session='cal'")
        report = gt.evaluate(self.db, 'cal', 'test')
        self.assertEqual((report['status'], report['stage']), ('insufficient_reference', 'calibration'))
        self.assertEqual(report['calibration_reference_coverage'], {})
        self.assertIsNone(report['scores'])

    def test_export_rejects_truncated_counts_wrong_session_and_bad_records(self):
        doc = dict(export_version=2, session=dict(id='cal', records=1, annotation_count=0),
                   records=[{'seq': 0, 'raw_hex': frame(0, 'near').hex()}], annotations=[])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.json'
            for changes, error in [
                ({'export_version': 3}, 'version'),
                ({'records': []}, 'record count'),
                ({'annotations': [{}]}, 'annotations'),
                ({'session': dict(doc['session'], annotation_count=1),
                  'annotations': [{'session': 'other'}]}, 'annotations'),
                ({'records': [{'seq': 0, 'raw_hex': 'f' * 639}]}, 'hex length'),
                ({'records': [{'seq': 0, 'raw_hex': 'z' * 640}]}, 'invalid raw hex'),
            ]:
                with self.subTest(error=error):
                    path.write_text(json.dumps({**doc, **changes}), encoding='utf-8')
                    with self.assertRaisesRegex(ValueError, error):
                        gt.read_export(path)

    def test_cli_reads_saved_database_without_modification(self):
        self.session('cal', 'near', interval=500, size=2048)
        self.session('test', 'far', interval=500)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.sqlite3'
            self.db.commit()
            disk = sqlite3.connect(path)
            try:
                self.db.backup(disk)
            finally:
                disk.close()
            original = path.read_bytes()
            result = subprocess.run([sys.executable, gt.__file__, '--history', str(path),
                                     '--calibration', 'cal', '--heldout', 'test'],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['scores']['profile']['correct'], 4)
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.iterdir()), [path])

