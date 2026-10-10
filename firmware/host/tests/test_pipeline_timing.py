"""Exercise the actual sender with local synthetic snapshots and no network."""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipeline as P

class PipelineTimingTests(unittest.TestCase):
    def test_host_sender_does_not_publish_temperature_deviation_assessments(self):
        snapshot = {
            'health': {name: {'status': 'offline', 'hz': 0.0} for name in
                       ('radar', 'thermal', 'csi')},
            'body': {'head_temp': {'estimate': {
                'core_f': 98.0, 'status': {'state': 'above typical'},
                'unusualness': {'pct': 90.0}}}},
        }
        with patch.object(sys, 'argv', ['pipeline.py', '--seconds', '1', '--api-key', 'test-only']), \
             patch.object(P, 'read_snapshot', return_value=snapshot), \
             patch.object(P, 'post', return_value=(202, {'accepted': 0})) as post, \
             patch.object(P.time, 'monotonic', side_effect=[0., 0., 2.]), \
             patch.object(P.time, 'sleep'), patch('sys.stdout', new_callable=io.StringIO):
            P.main()
        self.assertFalse(any('/v1/assessments' in call.args[0]
                             for call in post.call_args_list))

    def test_device_timestamps_reach_telemetry_envelopes(self):
        snapshot={
            'health':{k:{'status':'ok','hz':100.,'device_t_us':t} for k,t in
                      [('radar',1234000),('thermal',2345000),('csi',3456000)]},
            'radar':{'presence':True,'distance_m':.9,'heart_rate_bpm':72.,'respiration_rpm':15.},
            'thermal':{'max':30.,'min':22.},
            'csi':{'amps':[10.]*64,'rssi':-50},
            'csi_motion':{'energy':.5},
            'csi_vitals':{'breathing_rpm':15.,'breathing_confidence':.8},
        }
        with patch.object(sys,'argv',['pipeline.py','--seconds','1','--api-key','test-only']), \
             patch.object(P,'read_snapshot',return_value=snapshot), \
             patch.object(P,'post',return_value=(202,{'accepted':3})) as post, \
             patch.object(P.time,'monotonic',side_effect=[0.,0.,2.]), \
             patch.object(P.time,'sleep'), patch('sys.stdout',new_callable=io.StringIO):
            P.main()
        envelopes=post.call_args_list[0].args[1]
        self.assertEqual({e['source']:e['device_monotonic_ms'] for e in envelopes},
                         {'radar':1234,'thermal':2345,'wifi_csi':3456})
        heartbeat=post.call_args_list[1].args[1]
        self.assertIn('wifi_csi',heartbeat['sources_seen'])
