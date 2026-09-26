"""Vitals estimator behaviour on signals with known ground truth.

Every case here corresponds to a bug that actually occurred while building the
estimator. The negative cases matter more than the positive ones: a vitals
estimator that reports a confident wrong number is worse than one that reports
nothing.
"""

import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vitals  # noqa: E402


def synth(breath_hz, heart_hz, heart_amp, noise=0.05, seconds=48, fs=25.0, seed=7):
    random.seed(seed)
    est = vitals.VitalsEstimator()
    t0 = time.monotonic()
    for i in range(int(seconds * fs)):
        t = t0 + i / fs
        v = 3.0 * math.sin(2 * math.pi * breath_hz * t) if breath_hz else 0.0
        h = heart_amp * math.sin(2 * math.pi * heart_hz * t) if heart_hz else 0.0
        est.add(t, [20.0 + v + h + random.gauss(0, noise) for _ in range(64)])
    return est.estimate()


def approx(actual, expected, tol):
    return actual is not None and abs(actual - expected) <= tol


def test_breathing_rates():
    for hz, expect in ((0.25, 15.0), (0.20, 12.0), (0.30, 18.0)):
        breath, _ = synth(hz, 1.2, 1.0)
        assert approx(breath.rate, expect, 1.0), (hz, breath)


def test_heart_rates():
    for b_hz, h_hz, expect in ((0.25, 1.2, 72.0), (0.20, 1.10, 66.0), (0.30, 1.6, 96.0)):
        _, heart = synth(b_hz, h_hz, 1.0)
        assert approx(heart.rate, expect, 3.0), (h_hz, heart)


def test_no_heart_signal_reports_nothing():
    """Breathing present, no cardiac component. Must not invent one."""
    _, heart = synth(0.25, None, 0.0)
    assert heart.rate is None, heart


def test_pure_noise_reports_nothing():
    """The estimator must not find rhythm in noise."""
    breath, heart = synth(None, None, 0.0, noise=1.0)
    assert breath.rate is None, breath
    assert heart.rate is None, heart


def test_breathing_harmonic_is_rejected():
    """A 'heart rate' at exactly 5x the breathing rate is an artefact.

    This is the documented failure mode: a periodic component sitting on a
    breathing harmonic looks exactly like a plausible heart rate. 0.25 Hz
    breathing puts its 5th harmonic at 75 bpm.
    """
    _, heart = synth(0.25, 1.25, 1.0)
    assert heart.rate is None, heart


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_"):
            continue
        try:
            fn()
            print(f"PASS {name}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL {name}: {exc}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
