"""Displayed rates use distinct, quality-weighted observations and reject spikes."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vitals_select as V


class RateSmoothingTests(unittest.TestCase):
    def test_radar_is_preferred_for_both_rates_through_one_point_five_metres(self):
        radar = {'heart_rate_bpm': 72, 'respiration_rpm': 15}
        csi = {'heart_rate_bpm': 80, 'breathing_rpm': 18}
        inside = V.select(radar, csi, 1.5)
        self.assertEqual(inside['heart_source'], 'radar')
        self.assertEqual(inside['respiration_source'], 'radar')
        outside = V.select(radar, csi, 1.51)
        self.assertEqual(outside['heart_source'], 'wifi_csi')
        self.assertEqual(outside['respiration_source'], 'wifi_csi')

    def test_csi_disagreement_does_not_downweight_in_range_radar(self):
        smooth = V.Smoother()
        selected = V.select(
            {'heart_rate_bpm': 72, 'respiration_rpm': 15},
            {'heart_rate_bpm': 105, 'breathing_rpm': 24},
            0.8, smooth, now=1.0,
            sample_times={('radar', 'heart'): 1.0, ('radar', 'resp'): 1.0,
                          ('wifi_csi', 'heart'): 1.0, ('wifi_csi', 'resp'): 1.0},
            health={'radar': {'hz': 8.0}, 'csi': {'hz': 25.0}},
        )
        self.assertEqual(selected['heart_source'], 'radar')
        self.assertEqual(selected['respiration_source'], 'radar')
        self.assertEqual(smooth.series['heart'][-1][2], 1.0)
        self.assertEqual(smooth.series['resp'][-1][2], 1.0)

    def test_published_rate_changes_only_after_four_seconds(self):
        smooth = V.Smoother()
        for t, value in [(0, 70), (1, 72), (2, 71)]:
            smooth.add('heart', value, now=t, source='radar', quality=1)
        first = smooth.estimate('heart', now=2)
        self.assertIsNotNone(first)
        smooth.add('heart', 76, now=3, source='radar', quality=1)
        self.assertEqual(smooth.estimate('heart', now=3)['value'], first['value'])
        smooth.add('heart', 74, now=6, source='radar', quality=1)
        self.assertNotEqual(smooth.estimate('heart', now=6)['value'], first['value'])

    def test_low_quality_spike_does_not_replace_stable_heart_rate(self):
        smooth = V.Smoother()
        for t in (0, 1, 2):
            smooth.add('heart', 60, now=t, source='radar', quality=1)
        self.assertEqual(smooth.estimate('heart', now=2)['value'], 60)
        smooth.add('heart', 90, now=3, source='radar', quality=.1)
        smooth.add('heart', 60, now=4, source='radar', quality=1)
        smooth.add('heart', 60, now=6, source='radar', quality=1)
        self.assertLessEqual(smooth.estimate('heart', now=6)['value'], 65)

    def test_sustained_change_moves_gradually(self):
        smooth = V.Smoother()
        for t in (0, 1, 2):
            smooth.add('heart', 60, now=t, source='radar', quality=1)
        self.assertEqual(smooth.estimate('heart', now=2)['value'], 60)
        for t in (3, 4, 5, 6):
            smooth.add('heart', 90, now=t, source='radar', quality=1)
        next_rate = smooth.estimate('heart', now=6)['value']
        self.assertGreater(next_rate, 60)
        self.assertLess(next_rate, 80)

    def test_missing_reading_clears_display(self):
        smooth = V.Smoother()
        for t in (0, 1, 2):
            smooth.add('resp', 15, now=t, source='radar', quality=1)
        self.assertIsNotNone(smooth.estimate('resp', now=2))
        smooth.add('resp', None, now=3, source='radar', quality=1)
        self.assertIsNone(smooth.estimate('resp', now=3))

    def test_same_sample_timestamp_never_counts_twice(self):
        smooth = V.Smoother()
        for _ in range(12):
            smooth.add('heart', 72, now=1, source='radar', quality=1)
        self.assertIsNone(smooth.estimate('heart', now=1))

    def test_heart_display_requires_same_source_breathing_evidence(self):
        smooth = V.Smoother()
        for t in range(5):
            selected = V.select({'heart_rate_bpm': 90, 'respiration_rpm': None},
                                None, .8, smooth,
                                sample_times={('radar', 'heart'): float(t)},
                                now=float(t))
        self.assertNotIn('heart_rate_bpm', selected['estimate'])
