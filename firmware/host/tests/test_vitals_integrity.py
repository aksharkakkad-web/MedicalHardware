"""Regressions for clock provenance, freshness and conservative corroboration."""
import math
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge as B
import confidence as C
import radar_decode as R
import stream.frames as F
import vitals
import vitals_select as V


def radar(t=1_000_000, present=True, distance=.9, hr=72.):
    return F.RadarFrame(t, present, distance, 15., hr)


def thermal(t=1_000_000, warm=False):
    px=[22.]*768
    if warm:
        for y in range(8,16):
            for x in range(12,20): px[y*32+x]=32.
    return F.ThermalFrame(t,px)


def packet(mid, data):
    frame=bytes([1])+struct.pack('>HHH',1,len(data),mid)+bytes([0])+data
    crc=0
    for b in frame: crc ^= b
    return frame+bytes([crc])


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.clock=patch('time.monotonic',return_value=100.)
        self.now=self.clock.start()
        self.addCleanup(self.clock.stop)
        self.env=patch.dict('os.environ', {'NTFY_TOPIC':''})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_csi_uses_device_sample_time_despite_host_burst(self):
        s=B.State(True)
        s.apply(F.CsiFrame(1_000_000,-50,[3,4]*64))
        s.apply(F.CsiFrame(1_040_000,-50,[3,4]*64))
        self.assertEqual([t for t,a in s.vitals.samples],[1.,1.04])

    def test_csi_device_reboot_discards_previous_window(self):
        s=B.State(True)
        s.apply(F.CsiFrame(50_000_000,-50,[3,4]*64))
        s.apply(F.CsiFrame(1_000_000,-50,[3,4]*64))
        self.assertEqual(len(s.vitals.samples),1)

    def test_csi_long_gap_discards_previous_window(self):
        e=vitals.VitalsEstimator()
        e.add(1.,[1.]*64); e.add(10.,[2.]*64)
        self.assertEqual(len(e.samples),1)

    def test_stopped_stream_has_no_selected_or_smoothed_vitals(self):
        s=B.State(True); s.apply(radar())
        for _ in range(10): s.snapshot()
        self.now.return_value=104.
        snap=s.snapshot()
        self.assertIsNone(snap['vitals']['heart_rate_bpm'])
        self.assertEqual(snap['vitals']['estimate'],{})
        self.assertEqual(snap['health']['radar']['hz'],0.)

    def test_refreshes_do_not_manufacture_smoothing_samples(self):
        s=B.State(True); s.apply(radar())
        for _ in range(10): snap=s.snapshot()
        self.assertNotIn('heart_rate_bpm',snap['vitals']['estimate'])

    def test_smoother_drops_missing_and_old_values(self):
        sm=V.Smoother()
        for t in range(5): sm.add('heart',72.,now=float(t))
        self.assertIsNotNone(sm.estimate('heart',now=4.))
        self.assertIsNone(sm.estimate('heart',now=10.))
        sm.add('heart',None,now=10.)
        self.assertIsNone(sm.estimate('heart',now=10.))

    def test_unknown_range_does_not_crash_or_claim_in_range(self):
        sel=V.select({'heart_rate_bpm':72.},None,None)
        self.assertEqual(sel['heart_rate_bpm'],72.)
        self.assertIn('unknown',sel['heart_reason'])

    def test_invalid_values_cannot_win_selection(self):
        for value in (float('nan'),float('inf'),0.,-1.):
            sel=V.select({'heart_rate_bpm':value},None,.9)
            self.assertIsNone(sel['heart_rate_bpm'])

    def test_absent_comparator_is_not_agreement(self):
        sel=V.select({'heart_rate_bpm':72.,'respiration_rpm':15.},None,.9)
        self.assertIsNone(sel['agree'])
        cf=C.vitals_confidence(sel,{'radar':{'hz':8.}},.9)
        self.assertFalse(any(f['why']=='instruments agree' for f in cf['factors']))
        self.assertFalse(cf['calibrated'])
        self.assertEqual(cf['kind'],'heuristic_quality_score')

    def test_no_sensors_means_unknown_not_empty(self):
        self.assertEqual(B.State(True).snapshot()['fusion']['verdict'],'unknown')

    def test_stale_thermal_never_vetoes_fresh_radar(self):
        s=B.State(True); s.apply(thermal())
        self.now.return_value=104.; s.apply(radar(5_000_000))
        snap=s.snapshot()
        self.assertEqual(snap['radar']['heart_rate_bpm'],72.)
        self.assertEqual(snap['fusion']['thermal_evidence'],'unavailable')

    def test_nan_thermal_is_unavailable_not_negative_evidence(self):
        s=B.State(True); f=thermal(); f.pixels=[float('nan')]*768
        s.apply(f); s.apply(radar())
        snap=s.snapshot()
        self.assertEqual(snap['fusion']['thermal_evidence'],'unavailable')
        self.assertEqual(snap['radar']['heart_rate_bpm'],72.)

    def test_unaligned_thermal_never_vetoes_radar(self):
        s=B.State(True); s.apply(thermal(1_000_000)); s.apply(radar(4_000_000))
        snap=s.snapshot()
        self.assertEqual(snap['radar']['heart_rate_bpm'],72.)
        self.assertFalse(snap['fusion']['time_aligned'])

    def test_flat_scene_withholds_vitals_but_does_not_prove_furniture(self):
        s=B.State(True); s.apply(thermal()); s.apply(radar())
        snap=s.snapshot()
        self.assertIsNone(snap['radar']['heart_rate_bpm'])
        self.assertIn('unconfirmed',snap['radar']['vitals_withheld'])
        self.assertEqual(snap['fusion']['presence_status'],'unconfirmed')

    def test_stale_csi_estimate_not_revived_by_live_radar(self):
        s=B.State(True); s.apply(F.CsiFrame(1_000_000,-50,[3,4]*64))
        s.vitals_out={'heart_rate_bpm':72.,'breathing_rpm':15.}
        self.now.return_value=104.; s.apply(radar(5_000_000,hr=None))
        self.assertIsNone(s.snapshot()['vitals']['heart_rate_bpm'])

    def test_decoder_log_traffic_does_not_keep_vitals_alive(self):
        d=R.RadarDecoder()
        d.feed(packet(R.ID_CLOUD,struct.pack('<I',1)))
        d.feed(packet(R.ID_HEART,struct.pack('<f',72.)))
        self.assertEqual(d.state.heart_rate_bpm,72.)
        self.now.return_value=104.
        d.feed(packet(R.ID_CLOUD,struct.pack('<I',1)))
        d.feed(packet(R.ID_LOG,b'alive'))
        self.assertIsNone(d.state.heart_rate_bpm)

    def test_decoder_reacquisition_cannot_reuse_previous_person_vitals(self):
        d=R.RadarDecoder()
        d.feed(packet(R.ID_CLOUD,struct.pack('<I',1)))
        d.feed(packet(R.ID_HEART,struct.pack('<f',72.)))
        d.feed(packet(R.ID_CLOUD,struct.pack('<I',0)))
        d.feed(packet(R.ID_CLOUD,struct.pack('<I',1)))
        self.assertIsNone(d.state.heart_rate_bpm)

    def test_decoder_unknown_presence_and_nonfinite_vitals(self):
        d=R.RadarDecoder(); d.feed(packet(R.ID_LOG,b'alive'))
        self.assertIsNone(d.state.presence)
        d.feed(packet(R.ID_CLOUD,struct.pack('<I',1)))
        d.feed(packet(R.ID_HEART,struct.pack('<f',float('inf'))))
        self.assertIsNone(d.state.heart_rate_bpm)



class BoundaryTests(unittest.TestCase):
    def test_notification_describes_observation_without_diagnosis(self):
        import posture_watch as P
        from types import SimpleNamespace
        event=SimpleNamespace(kind='horizontal',headline='Sustained horizontal posture',limitations=['Cannot distinguish lying down from a fall'])
        with patch.dict('os.environ', {'NTFY_TOPIC':'unit-test-only'}, clear=True), patch.object(P.urllib.request,'urlopen') as send:
            send.return_value.__enter__.return_value.status=200
            P.notify(event)
            request=send.call_args.args[0]
            self.assertEqual(request.get_header('Title'),'Sustained horizontal posture')
            self.assertNotIn('has fallen',request.data.decode())
            self.assertIn('cannot determine',request.data.decode())

    def test_confidence_always_identifies_uncalibrated_score(self):
        score=C.vitals_confidence(None,{},None)
        self.assertFalse(score['calibrated'])

    def test_short_csi_history_is_collecting(self):
        with patch('time.monotonic',return_value=100.):
            e=vitals.VitalsEstimator()
            for i in range(250):
                t=i/25
                e.add(t,[20+3*math.sin(2*math.pi*.25*t)]*64)
            self.assertEqual(e.estimate()[0].reason,'collecting')

    def test_nonoverlapping_estimates_are_not_corroborated(self):
        sel=V.select({'heart_rate_bpm':72.,'respiration_rpm':15.},
                     {'heart_rate_bpm':72.,'breathing_rpm':15.},.9,
                     sample_times={('radar','heart'):100.,('radar','resp'):100.,
                                   ('wifi_csi','heart'):97.,('wifi_csi','resp'):97.},now=100.)
        self.assertIsNone(sel['agree'])

class ReviewRegressions(unittest.TestCase):
    def test_radar_log_does_not_refresh_presence_timestamp(self):
        with patch('time.monotonic',return_value=100.) as now:
            s=B.State(True)
            s.apply(F.RadarRawFrame(1_000_000,packet(R.ID_CLOUD,struct.pack('<I',1))))
            now.return_value=102.
            s.apply(thermal(3_000_000,warm=True))
            s.apply(F.RadarRawFrame(3_000_000,packet(R.ID_LOG,b'alive')))
            snap=s.snapshot()
            self.assertFalse(snap['fusion']['time_aligned'])
            self.assertEqual(snap['fusion']['device_skew_s'],2.)

    def test_reboot_during_snapshot_does_not_publish_prior_epoch(self):
        with patch('time.monotonic',return_value=100.), patch.dict('os.environ',{'NTFY_TOPIC':''}):
            s=B.State(True)
            s.apply(F.CsiFrame(50_000_000,-50,[3,4]*64))
            s.apply(radar(50_000_000)); s.apply(thermal(50_000_000,True))
            original=B.body_model.analyse
            def reboot(*args):
                s.apply(F.CsiFrame(1_000_000,-50,[3,4]*64))
                return original(*args)
            with patch.object(B.body_model,'analyse',side_effect=reboot):
                snap=s.snapshot()
            self.assertIsNone(snap['vitals']['heart_rate_bpm'])
            self.assertFalse(s.vitals_smoother.series.get('heart'))

    def test_capture_rate_is_unavailable_when_stats_stop(self):
        with patch('time.monotonic',return_value=100.) as now:
            s=B.State(True)
            s.apply(F.DeviceStats(1_000_000,100,0,0,100)); s.snapshot()
            now.return_value=101.
            s.apply(F.CsiFrame(2_000_000,-50,[3,4]*64))
            s.apply(F.DeviceStats(2_000_000,200,0,0,200))
            self.assertEqual(s.snapshot()['csi_captured_hz'],100.)
            now.return_value=105.
            s.apply(F.CsiFrame(6_000_000,-50,[3,4]*64))
            self.assertIsNone(s.snapshot()['csi_captured_hz'])

class EpochEffectsTests(unittest.TestCase):
    def test_discarded_snapshot_does_not_publish_prior_body_or_vitals(self):
        with patch('time.monotonic',return_value=100.), patch.dict('os.environ',{'NTFY_TOPIC':''}):
            state=B.State(True)
            state.apply(F.CsiFrame(50_000_000,-50,[3,4]*64))
            state.apply(radar(50_000_000)); state.apply(thermal(50_000_000,True))
            state.skin_hist=[(100.,90.)]*5
            original=B.body_model.analyse
            def reboot(*args):
                state.apply(F.CsiFrame(1_000_000,-50,[3,4]*64))
                return original(*args)
            with patch.object(B.body_model,'analyse',side_effect=reboot):
                snap=state.snapshot()
            self.assertIsNone(snap.get('body'))
            self.assertIsNone(snap['vitals']['heart_rate_bpm'])
            self.assertNotIn('posture_events',snap)

class NotificationScopeTests(unittest.TestCase):
    def test_sensitive_motion_is_not_labelled_horizontal(self):
        from types import SimpleNamespace
        import posture_watch as P
        event=SimpleNamespace(kind='motion_change',detail='movement detected')
        with patch.dict('os.environ',{'NTFY_TOPIC':'test-only'},clear=True), patch.object(P.urllib.request,'urlopen') as send:
            send.return_value.__enter__.return_value.status=200
            P.notify(event)
        request=send.call_args.args[0]
        self.assertEqual(request.get_header('Title'),'Thermal motion change')
        self.assertNotIn('horizontal',request.data.decode())

if __name__=='__main__': unittest.main()
