"""Panel API and replay regression checks using disposable local databases."""
from contextlib import closing
import http.client
import json
from pathlib import Path
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import web_panel as panel
from panel_signal import measurements


def raw(timer, changed=False):
    data=bytearray(2048)
    struct.pack_into('<II',data,16,0x04041004,timer & 0xffffffff)
    for i in range(56):
        struct.pack_into('<hh',data,96+i*4,100+i*(10 if changed else 0),30)
    return bytes(data)


class ReplayTests(unittest.TestCase):
    def test_intervals_invalid_and_gaps(self):
        for interval in (100,200,500):
            result=measurements([(i,raw(i*interval*1000)) for i in range(20)],interval)
            self.assertAlmostEqual(result['summary']['sample_rate_hz'],1000/interval)
            self.assertAlmostEqual(result['summary']['duration_s'],19*interval/1000)
            self.assertEqual(result['summary']['gap_count'],0)
        result=measurements([(0,raw(0)),(1,raw(100000)),(2,b'bad'),(3,raw(200000)),(4,raw(600000))])
        self.assertEqual(result['summary']['invalid_records'],1)
        self.assertIsNone(result['samples'][3]['smooth'])
        self.assertTrue(result['samples'][4]['gap'])
        self.assertIsNone(result['samples'][4]['smooth'])

    def test_reset_wrap_and_empty(self):
        result=measurements([(0,raw(2**32-100000)),(1,raw(0))])
        self.assertAlmostEqual(result['summary']['duration_s'],.1)
        with self.assertRaises(ValueError):measurements([(0,raw(100000)),(1,raw(0))])
        self.assertIsNone(measurements([])['summary']['duration_s'])


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.original=panel.HISTORY
        panel.HISTORY=Path(self.temp.name)/'history.sqlite3'
        panel.initialize()
        with closing(panel.db()) as c,c:
            for sid in ('test-session','empty-session'):
                c.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)',(sid,1000,1002,'captured',json.dumps({'interval_ms':100}),''))
            c.executemany('INSERT INTO records VALUES(?,?,?,?)', [('test-session',i,raw(i*100000,i>10),'{}') for i in range(21)])
        self.server=panel.ThreadingHTTPServer(('127.0.0.1',0),panel.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        panel.HISTORY=self.original;self.temp.cleanup()

    def request(self,path,body=None,token=True,origin=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        headers={}
        if body is not None:
            headers={'Content-Type':'application/json'}
            if token:headers['X-Panel-Token']=panel.WRITE_TOKEN
            if origin:headers['Origin']=origin
        c.request('POST' if body is not None else 'GET',path,body=json.dumps(body) if body is not None else None,headers=headers)
        r=c.getresponse();data=r.read();status=r.status;c.close()
        return status,json.loads(data)

    def test_points_routes_round_trip_and_provenance(self):
        for pid,x in [('p1',0),('p2',1)]:
            status,_=self.request('/api/points',{'id':pid,'label':pid,'region':'R08','x':x,'y':0})
            self.assertEqual(status,201)
        status,value=self.request('/api/routes',{'label':'walk','points':['p1','p2']})
        self.assertEqual(status,201)
        route=self.request('/api/routes')[1]['routes'][0]
        self.assertEqual(route['points'],['p1','p2'])
        self.assertEqual(route['context']['point_snapshots'][1]['x'],1)
        self.assertIn('floorplan_sha256',route['context']['map_sources'])
        self.assertEqual(self.request('/api/routes',{'label':'bad','points':['p1','missing']})[0],400)

    def test_annotations_and_export_keep_raw_bytes(self):
        payload={'start_s':.2,'end_s':1.2,'activity':'walking','kind':'observed','timing_uncertainty_s':.3}
        self.assertEqual(self.request('/api/sessions/test-session/annotations',payload)[0],201)
        value=self.request('/api/sessions/test-session/export')[1]
        self.assertEqual(bytes.fromhex(value['records'][20]['raw_hex']),raw(2000000,True))
        self.assertEqual(value['annotations'][0]['context']['timing_uncertainty_s'],.3)
        self.assertIsNone(value['map_at_capture'])
        for bad in ({'start_s':-1},{'end_s':9},{'point_id':'missing'},{'activity':'made up'},{'end_s':.1},{'timing_uncertainty_s':float('nan')}):
            self.assertEqual(self.request('/api/sessions/test-session/annotations',{**payload,**bad})[0],400)
        self.assertEqual(self.request('/api/sessions/empty-session/annotations',payload)[0],400)

    def test_writes_require_token_and_valid_body(self):
        self.assertEqual(self.request('/api/points',{'label':'p','x':0,'y':0},token=False)[0],403)
        self.assertEqual(self.request('/api/points',{'label':'p','x':0,'y':0},origin='http://other.local')[0],403)
        self.assertEqual(self.request('/api/points',[])[0],400)
        for value in (float('nan'),float('inf'),False,999):
            self.assertEqual(self.request('/api/points',{'label':'p','x':value,'y':0})[0],400)
        self.assertEqual(self.request('/api/captures',{'seconds':4})[0],400)

    def test_health_empty_unknown_and_detail_beyond_first_page(self):
        status,h=self.request('/api/health');self.assertEqual(status,200)
        self.assertTrue(h['capture_enabled']);self.assertEqual(h['records'],21)
        self.assertEqual(self.request('/api/sessions/no-such-session')[0],404)
        self.assertEqual(self.request('/api/sessions/empty-session/measurements')[1]['summary']['valid_records'],0)
        with closing(panel.db()) as c,c:
            c.executemany('INSERT INTO sessions VALUES(?,?,?,?,?,?)',[(f'extra-{i}',2000+i,2001+i,'failed','{}','') for i in range(101)])
        self.assertEqual(len(self.request('/api/sessions')[1]['sessions']),100)
        self.assertEqual(self.request('/api/sessions/test-session')[0],200)
        self.assertEqual(self.request('/api/sessions?offset=100')[1]['total'],103)

    def test_theme_stylesheet_is_served(self):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        c.request('GET','/theme.css')
        r=c.getresponse(); body=r.read().decode(); c.close()
        self.assertEqual(r.status,200)
        self.assertIn('[data-theme="dark"]',body)

    def test_session_delete_removes_records_and_annotations(self):
        self.assertEqual(self.request('/api/sessions/test-session/delete',{})[0],201)
        self.assertEqual(self.request('/api/sessions/test-session')[0],404)

    def test_capture_snapshot_keeps_identity_and_signal(self):
        for sid in ('empty-session', 'test-session'):
            status, snapshot = self.request('/api/captures/' + sid)
            self.assertEqual(status, 200)
            self.assertEqual(snapshot['id'], sid)
            self.assertEqual(snapshot['session']['id'], sid)
            self.assertIn('samples', snapshot)
            self.assertFalse(snapshot['paused'])
        self.assertEqual(len(snapshot['samples']), 21)

    def test_live_cursor_incremental_no_history_replay(self):
        job = panel.CaptureJob('empty-session', 60, 100)
        with patch.object(panel, 'LATEST_CAPTURE', job):
            for seq in range(5):
                job._append(raw(seq * 100000), seq)
            with patch.object(panel, 'replay', side_effect=AssertionError('Full replay called')):
                status, first = self.request('/api/captures/empty-session/live?after=-1')
                self.assertEqual(status, 200)
                self.assertTrue(first['reset'])
                self.assertEqual(first['next_seq'], 4)
                self.assertEqual(len(first['samples']), 5)
                job._append(raw(500000, True), 5)
                update = self.request('/api/captures/empty-session/live?after=4')[1]
                self.assertFalse(update['reset'])
                self.assertEqual([p['seq'] for p in update['samples']], [5])
                self.assertGreater(update['samples'][0]['smooth'], 0)
                self.assertLess(update['last_sample_age_s'], 2)
                self.assertEqual(self.request('/api/captures/empty-session/live?after=5')[1]['samples'], [])
        self.assertEqual(self.request('/api/captures/empty-session/live?after=bad')[0], 400)

    def test_live_window_bounded_and_stale_cursor_reset(self):
        job = panel.CaptureJob('test-session', 1800, 100)
        with job.live_lock:
            for seq in range(11000):
                job.live_samples.append({'seq': seq, 'valid': True, 'seconds': seq / 10, 'smooth': 0})
        with patch.object(panel, 'LATEST_CAPTURE', job):
            result = self.request('/api/captures/test-session/live?after=0')[1]
            self.assertTrue(result['reset'])
            self.assertEqual(len(result['samples']), 600)
            self.assertEqual(result['next_seq'], 10999)
            self.assertEqual(result['samples'][0]['seq'], 10400)
        # A restart recovers a bounded window from disk without a cached job.
        with patch.object(panel, 'LATEST_CAPTURE', None):
            result = self.request('/api/captures/test-session/live')[1]
            self.assertTrue(result['reset'])
            self.assertEqual(len(result['samples']), 21)

    def test_capture_signal_error_does_not_hide_controls(self):
        with closing(panel.db()) as c, c:
            c.execute('UPDATE records SET raw=? WHERE session=? AND seq=2',
                      (raw(0), 'test-session'))
        status, snapshot = self.request('/api/captures/test-session')
        self.assertEqual(status, 200)
        self.assertEqual(snapshot['id'], 'test-session')
        self.assertIn('timer', snapshot['signal_error'])
        self.assertEqual(self.request('/api/sessions/test-session/measurements')[0], 422)

    def test_delete_running_rejected_paused_and_stopping_joined(self):
        job = Mock(session='test-session', pause_requested=False, remaining=20)
        job.thread.is_alive.return_value = True
        job.stop_requested.is_set.return_value = False
        with patch.object(panel, 'ACTIVE_CAPTURE', job):
            self.assertEqual(self.request('/api/sessions/test-session/delete', {})[0], 409)
            job.request_stop.assert_not_called()
            job.pause_requested = True
            snapshot = self.request('/api/captures/test-session')[1]
            self.assertTrue(snapshot['paused'])
            self.assertEqual(snapshot['remaining_s'], 20)
            # Failed bounded join retains all data.
            self.assertEqual(self.request('/api/sessions/test-session/delete', {})[0], 409)
            self.assertEqual(self.request('/api/sessions/test-session')[1]['session']['records'], 21)
            job.pause_requested = False
            job.stop_requested.is_set.return_value = True
            job.thread.join.side_effect = lambda **kw: setattr(job.thread.is_alive, 'return_value', False)
            self.assertEqual(self.request('/api/sessions/test-session/delete', {})[0], 201)
            job.thread.join.assert_called_with(timeout=12)
        self.assertEqual(self.request('/api/sessions/test-session')[0], 404)


if __name__=='__main__':unittest.main()
