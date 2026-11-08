import copy
import importlib.util
import json
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('dashboard', Path(__file__).resolve().parents[1] / 'server.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.s = app.State()

    def test_invalid_combined_control_does_not_change_mode(self):
        with self.assertRaises(ValueError):
            self.s.control({'mode': 'live', 'speed': 99})
        self.assertEqual(self.s.mode, 'demo')

    def test_demo_pause_speed_and_completion(self):
        self.s.reset('测试目标', 'research')
        self.s.control({'paused': True})
        self.s.tick(30)
        self.assertEqual(self.s.snapshot()['elapsed'], 0)
        self.s.control({'paused': False, 'speed': 2})
        self.s.tick(32)
        result = self.s.snapshot()
        self.assertEqual(result['metrics']['completed'], 8)
        self.assertEqual(result['metrics']['progress'], 100)
        self.assertTrue(all(e['source'] == 'demo' for e in result['events']))

    def test_mode_isolation_and_external_event(self):
        with self.assertRaises(ValueError):
            self.s.ingest({'agent':'CODEX', 'type':'started'})
        self.s.control({'mode':'live'})
        self.s.tick(500)
        result = self.s.snapshot()
        self.assertEqual(result['metrics']['tokens'], 0)
        self.assertEqual(result['events'], [])
        self.s.ingest({'agent':'CODEX','type':'started','task':'示例外部任务'})
        self.s.ingest({'agent':'CODEX','type':'progress','progress':45,'tokens_delta':123})
        result = self.s.snapshot()
        self.assertEqual(result['agents'][2]['progress'],45)
        self.assertEqual(result['metrics']['tokens'],123)
        self.assertEqual(result['events'][-1]['source'],'external')
        self.s.ingest({'agent':'CODEX','type':'completed','progress':5})
        self.assertEqual(self.s.snapshot()['agents'][2]['progress'],100)

    def test_invalid_input_does_not_change_state(self):
        self.s.control({'mode':'live'})
        before = copy.deepcopy(self.s.agents)
        invalid = [dict(agent='UNKNOWN', type='started'),dict(agent='CODEX',type='shell'),
                   dict(agent='CODEX',type='progress',progress=float('nan')),
                   dict(agent='CODEX',type='progress',progress=True),
                   dict(agent='CODEX',type='progress',progress=-1),
                   dict(agent='CODEX',type='progress',tokens_delta=1.2),
                   dict(agent='CODEX',type='started',message='x'*401)]
        for body in invalid:
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.s.ingest(body)
        self.assertEqual(self.s.agents,before)
        self.assertEqual(self.s.events,[])

    def test_failure_heartbeat_and_recovery(self):
        self.s.control({'mode':'live'})
        self.s.ingest({'agent':'SCOUT','type':'error','message':'来源暂不可用'})
        self.assertEqual(self.s.snapshot()['agents'][1]['status'],'error')
        self.s.ingest({'agent':'SCOUT','type':'started'})
        self.s.agents[1]['last_seen'] = '2020-01-01T00:00:00+00:00'
        self.assertEqual(self.s.snapshot()['agents'][1]['status'],'stale')
        self.s.ingest({'agent':'SCOUT','type':'heartbeat'})
        self.assertEqual(self.s.snapshot()['agents'][1]['status'],'working')

    def test_bounded_feed_and_snapshot_is_copy(self):
        self.s.control({'mode':'live'})
        for _ in range(200):
            self.s.ingest({'agent':'RELAY','type':'heartbeat'})
        result = self.s.snapshot()
        self.assertEqual(len(result['events']),180)
        result['agents'][0]['status']='bad'
        self.assertEqual(self.s.agents[0]['status'],'idle')


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        cls.port=cls.server.server_address[1]
        cls.base=f'http://127.0.0.1:{cls.port}'
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self,path,body=None,headers=None):
        h={'Content-Type':'application/json'}
        h.update(headers or {})
        request=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
        try:
            with urllib.request.urlopen(request,timeout=3) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as error:
            return error.code,json.load(error)

    def test_health_and_missing_route(self):
        self.assertEqual(self.call('/healthz')[0],200)
        self.assertEqual(self.call('/unknown')[0],404)

    def test_cross_origin_and_host_rejected(self):
        self.assertEqual(self.call('/api/control',{'mode':'live'},{'Origin':'https://example.com'})[0],403)
        self.assertEqual(self.call('/api/state',headers={'Host':'example.com'})[0],403)

    def test_event_roundtrip_and_invalid_mission(self):
        self.assertEqual(self.call('/api/mission',{'title':'','scenario':'build'})[0],400)
        self.assertEqual(self.call('/api/mission',{'title':'示例','scenario':'unknown'})[0],400)
        self.assertEqual(self.call('/api/control',{'mode':'live'})[0],200)
        self.assertEqual(self.call('/api/ingest',{'agent':'CODEX','type':'progress','progress':35})[0],200)
        result=self.call('/api/state')[1]
        self.assertEqual(result['agents'][2]['progress'],35)
        self.assertEqual(self.call('/api/export')[1]['seq'],result['seq'])


if __name__=='__main__':
    unittest.main()
