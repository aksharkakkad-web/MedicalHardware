"""Confidence and unusualness behaviour.

Both numbers are easy to make look authoritative and hard to make honest, so
these tests pin the properties that keep them honest: a single bad condition
must dominate the confidence score, and unusualness must stay modest until
enough history exists to support a strong claim.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import confidence as C  # noqa: E402


def test_one_bad_factor_dominates():
    """Confidence is multiplicative, not averaged.

    A perfect sample rate must not rescue a body that is half out of frame.
    """
    good = C.confidence_pct([("a", 0.95, ""), ("b", 0.95, ""), ("c", 0.95, "")])
    mixed = C.confidence_pct([("a", 1.0, ""), ("b", 1.0, ""), ("c", 0.1, "")])
    assert good["pct"] > 80
    assert mixed["pct"] < 15, mixed
    assert mixed["limiting"] == "c"


def test_unusualness_needs_history():
    pct, why = C.unusualness_pct(3.0, 4)
    assert pct == 0.0
    assert "not enough history" in why


def test_small_baseline_is_capped():
    """A 20-sample history cannot support a 1-in-1000 claim."""
    small, why = C.unusualness_pct(4.0, 20)
    large, _ = C.unusualness_pct(4.0, 500)
    assert small <= 95.0, small
    assert large > small
    assert "capped" in why


def test_unusualness_rises_with_deviation():
    n = 200
    vals = [C.unusualness_pct(z, n)[0] for z in (0.5, 1.0, 2.0, 3.0)]
    assert vals == sorted(vals)
    assert vals[0] < 40
    assert vals[-1] > 95


def test_temperature_confidence_penalises_poor_conditions():
    good = C.temperature_confidence(
        {"fill_fraction": 1.0, "uncertainty_f": 2.1, "jitter_f": 1.0,
         "calibrated": True}, 60)
    far = C.temperature_confidence(
        {"fill_fraction": 0.45, "uncertainty_f": 4.6, "jitter_f": 6.0,
         "calibrated": False}, 12)
    assert good["pct"] > 50, good
    assert far["pct"] < 10, far


def test_uncalibrated_costs_confidence():
    base = {"fill_fraction": 1.0, "uncertainty_f": 2.1, "jitter_f": 1.0}
    cal = C.temperature_confidence({**base, "calibrated": True}, 60)
    uncal = C.temperature_confidence({**base, "calibrated": False}, 60)
    assert cal["pct"] > uncal["pct"]


def test_csi_vitals_score_below_radar():
    """One antenna cannot confirm the change was the person."""
    health = {"radar": {"hz": 8.0}, "csi": {"hz": 100.0}}
    radar = C.vitals_confidence(
        {"heart_rate_bpm": 72, "heart_source": "radar", "agree": True},
        health, 0.9)
    csi = C.vitals_confidence(
        {"heart_rate_bpm": 72, "heart_source": "wifi_csi", "agree": True},
        health, 3.0)
    assert radar["pct"] > csi["pct"], (radar, csi)


def test_disagreement_and_suspect_reduce_confidence():
    health = {"radar": {"hz": 8.0}, "csi": {"hz": 100.0}}
    ok = C.vitals_confidence(
        {"heart_rate_bpm": 72, "heart_source": "radar", "agree": True}, health, 0.9)
    bad = C.vitals_confidence(
        {"heart_rate_bpm": 72, "heart_source": "radar", "agree": False,
         "suspect": "heart rate without breathing"}, health, 0.9)
    assert bad["pct"] < ok["pct"] / 2, (ok, bad)


def test_no_reading_is_zero_not_default():
    assert C.vitals_confidence(None, {}, None)["pct"] == 0
    assert C.temperature_confidence(None, 0)["pct"] == 0


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
