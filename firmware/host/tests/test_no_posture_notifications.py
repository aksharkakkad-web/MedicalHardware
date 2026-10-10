"""The bench host must not generate posture alerts during live monitoring."""
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge
import posture_watch
import stream.frames as frames


class NoPostureNotificationTests(unittest.TestCase):
    def test_snapshot_keeps_body_position_without_posture_notification(self):
        state = bridge.State(True)
        pixels = [22.0] * 768
        for y in range(7, 19):
            for x in range(12, 20):
                pixels[y * 32 + x] = 33.0
        state.apply(frames.ThermalFrame(1_000_000, pixels))
        state.skin_hist = [(time.monotonic(), 91.4)] * 5

        event = SimpleNamespace(kind='horizontal', at=1.0, detail='old alert',
                                confidence_pct=50.0, prior_posture='upright', limitations=[])
        with patch.object(posture_watch.PostureWatcher, 'update', return_value=event) as update, \
             patch.object(posture_watch, 'notify', return_value=(False, 'test')) as notify:
            snapshot = state.snapshot()

        self.assertIn('body', snapshot)
        self.assertNotIn('posture_events', snapshot)
        estimate = snapshot['body']['head_temp']['estimate']
        self.assertNotIn('unusualness', estimate)
        self.assertNotIn('status', estimate)
        update.assert_not_called()
        notify.assert_not_called()
