"""Confidence in a reading, and how unusual it is.

These answer two different questions and are kept apart deliberately.

CONFIDENCE is about the measurement: how much do the conditions support this
number? It is built from factors that are individually observable - sample
rate, signal quality, how much of the body is in frame, whether independent
sensors agree, whether enough history exists - and every factor is reported
alongside the total, so a low score can be acted on rather than merely noted.

UNUSUALNESS is a statistical statement, not a diagnosis. Given this person's
own baseline and its measured spread, it answers: how rarely would a deviation
this large appear if nothing had changed? A two-tailed normal tail probability,
reported as a percentage.

  2.0 sigma -> about 95% - a deviation this big appears in 1 reading in 20
  3.0 sigma -> about 99.7%

What it is NOT is the probability that something is wrong with the person. That
would require labelled outcomes, and there are none. A reading can be highly
unusual because of a draught, a hat, or a shifted sensor.

Small baselines are corrected for. A spread estimated from 40 samples is itself
uncertain, so it is inflated and the reportable maximum is capped - claiming
99.9% from a handful of readings would be false precision.
"""

from __future__ import annotations

import math


def _erfc(x: float) -> float:
    return math.erfc(x)


def tail_probability(z: float) -> float:
    """Two-tailed probability of |Z| >= z under a normal distribution."""
    return _erfc(abs(z) / math.sqrt(2.0))


def unusualness_pct(z: float, n_samples: int) -> tuple[float, str]:
    """How rarely a deviation this large appears, as a percentage.

    The spread behind `z` was itself estimated from `n_samples`, so it is
    inflated for small n and the reported value is capped accordingly.
    """
    if n_samples < 10:
        return 0.0, "not enough history to judge"

    # Inflate the estimated spread for sampling error, shrinking toward 1 as
    # the baseline grows.
    inflation = 1.0 + 2.0 / math.sqrt(n_samples)
    z_eff = abs(z) / inflation

    pct = (1.0 - tail_probability(z_eff)) * 100.0

    # A baseline of n samples cannot support a claim rarer than about 1/n.
    cap = (1.0 - 1.0 / max(n_samples, 2)) * 100.0
    capped = min(pct, cap)
    note = (f"{z:.1f} sigma from baseline, adjusted to {z_eff:.1f} for a "
            f"{n_samples}-sample history")
    if capped < pct:
        note += f"; capped at {cap:.0f}% by history length"
    return round(capped, 1), note


def confidence_pct(factors: list[tuple[str, float, str]]) -> dict:
    """Combine 0-1 factors into a percentage.

    Multiplicative, not averaged: a single bad condition should dominate. A
    perfect sample rate does not rescue a body that is half out of frame, and
    averaging would let it.
    """
    if not factors:
        return {"pct": 0, "factors": [], "limiting": "nothing measured"}
    total = 1.0
    for _, v, _ in factors:
        total *= max(0.0, min(1.0, v))
    worst = min(factors, key=lambda f: f[1])
    return {
        "pct": round(total * 100, 1),
        "factors": [{"name": n, "score": round(v, 2), "why": w} for n, v, w in factors],
        "limiting": worst[0],
        "limiting_why": worst[2],
    }


def temperature_confidence(est: dict | None, baseline_n: int) -> dict:
    if not est:
        return confidence_pct([])
    f = []
    fill = est.get("fill_fraction", 0.0)
    f.append(("pixel fill", fill,
              f"forehead covers {fill*100:.0f}% of a pixel"))
    u = est.get("uncertainty_f") or 5.0
    # +/-1.8 F is the sensor's own floor; score against it.
    f.append(("uncertainty", min(1.0, 1.8 / u),
              f"+/-{u} F against a +/-1.8 F sensor floor"))
    jitter = est.get("jitter_f")
    if jitter is not None:
        f.append(("stability", max(0.0, 1.0 - jitter / 8.0),
                  f"raw readings spread {jitter} F"))
    f.append(("calibration", 1.0 if est.get("calibrated") else 0.55,
              "calibrated against a reference" if est.get("calibrated")
              else "uncalibrated skin-to-core offset"))
    f.append(("history", min(1.0, baseline_n / 40.0),
              f"{baseline_n} of 40 baseline readings"))
    return confidence_pct(f)


def vitals_confidence(selected: dict | None, health: dict, distance_m: float | None) -> dict:
    if not selected or selected.get("heart_rate_bpm") is None:
        return confidence_pct([])
    f = []
    src = selected.get("heart_source")
    if src == "radar":
        in_range = distance_m is not None and distance_m <= 1.5
        f.append(("range", 1.0 if in_range else 0.4,
                  f"target at {distance_m:.2f} m" if distance_m else "range unknown"))
        hz = health.get("radar", {}).get("hz", 0)
        f.append(("sample rate", min(1.0, hz / 8.0), f"radar at {hz:.1f} Hz"))
    else:
        hz = health.get("csi", {}).get("hz", 0)
        f.append(("sample rate", min(1.0, hz / 25.0), f"CSI at {hz:.1f} Hz"))
        f.append(("spatial selectivity", 0.4,
                  "one antenna cannot confirm the change was the person"))
    f.append(("cross-check", 1.0 if selected.get("agree") else 0.35,
              "instruments agree" if selected.get("agree")
              else "radar and Wi-Fi disagree"))
    if selected.get("suspect"):
        f.append(("plausibility", 0.3, selected["suspect"]))
    f.append(("validation", 0.6, "never checked against a reference device"))
    return confidence_pct(f)
