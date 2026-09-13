"""Choose which instrument to believe, and say when they disagree.

Neither instrument is validated against a reference device, so this is a
routing rule grounded in physics, not an accuracy ranking.

  - Radar is a 60 GHz beam with range gating. At 5 mm wavelength a
    sub-millimetre chest movement is a large fraction of a cycle. Within its
    working range it is the better instrument by a wide margin, and it knows
    which target it is measuring.
  - CSI is a 5.2 GHz whole-path measurement with one antenna and no spatial
    selectivity at all. Any motion anywhere along the link lands in the same
    number. It reaches further because it does not depend on a beam, but it
    cannot tell you that the change it saw was the person.

So: radar inside its stated range, CSI beyond it, and an explicit disagreement
flag whenever both are present and differ enough to matter.
"""

from __future__ import annotations

import time

# From the bring-up brief: vital signs need a nearly stationary subject within
# ~1.5 m for heart rate and ~2 m for respiration.
RADAR_HEART_RANGE_M = 1.5
RADAR_RESP_RANGE_M = 2.0

# Above these the two instruments are not describing the same thing.
HEART_DISAGREE_BPM = 10.0
RESP_DISAGREE_RPM = 4.0


def _pick(field, radar_val, csi_val, distance_m, radar_range_m):
    """Return (value, source, reason)."""
    radar_in_range = (
        radar_val is not None
        and distance_m is not None
        and distance_m <= radar_range_m
    )
    if radar_in_range:
        return radar_val, "radar", f"target at {distance_m:.2f} m, within {radar_range_m:g} m"
    if csi_val is not None:
        if distance_m is None:
            return csi_val, "wifi_csi", "no radar range available"
        if distance_m > radar_range_m:
            return csi_val, "wifi_csi", f"target at {distance_m:.2f} m, beyond radar range"
        return csi_val, "wifi_csi", "radar reported nothing usable"
    if radar_val is not None:
        # Out of range but the only reading there is. Hand it back labelled,
        # rather than dropping it silently.
        return radar_val, "radar", f"out of range ({distance_m:.2f} m) - treat with caution"
    return None, None, "neither instrument produced a reading"


# Rolling window for the smoothed estimate. Instantaneous readings from both
# instruments jump several bpm between frames, which is measurement noise rather
# than a changing pulse, so a plain median over a window is both steadier and
# closer to the truth than any single frame.
SMOOTH_WINDOW_S = 20.0
MIN_SMOOTH_SAMPLES = 5


class Smoother:
    """Median and spread of recent readings, per field."""

    def __init__(self) -> None:
        self.series: dict[str, list[tuple[float, float]]] = {}
        # Last good estimate per field, kept after the window empties so the
        # display never has to go blank. A blank tells the reader nothing; a
        # real reading with its age tells them exactly how much to trust it.
        self.last: dict[str, dict] = {}

    def add(self, field: str, value: float | None, now: float | None = None) -> None:
        if value is None:
            return
        now = now if now is not None else time.monotonic()
        s = self.series.setdefault(field, [])
        s.append((now, value))
        cutoff = now - SMOOTH_WINDOW_S
        self.series[field] = [(t, v) for t, v in s if t >= cutoff]

    def estimate(self, field: str, now: float | None = None) -> dict | None:
        now = now if now is not None else time.monotonic()
        # Prune here as well as in add(). Pruning only on insert meant a stream
        # that stopped kept its last samples forever and never aged - the
        # display would show a reading from a minute ago as if it were live.
        s = [(t, v) for t, v in (self.series.get(field) or []) if now - t <= SMOOTH_WINDOW_S]
        self.series[field] = s
        if len(s) < MIN_SMOOTH_SAMPLES:
            # Fall back to the last good estimate, aged. Never invented, never
            # zero - just the most recent real measurement and how old it is.
            prev = self.last.get(field)
            if prev:
                out = dict(prev)
                out["age_s"] = round(now - prev["_at"], 1)
                out["stale"] = out["age_s"] > 5.0
                out.pop("_at", None)
                return out
            return None
        vals = sorted(v for _, v in s)
        n = len(vals)
        median = vals[n // 2]
        # Interquartile range, so one wild frame does not widen the band.
        lo = vals[max(0, n // 4)]
        hi = vals[min(n - 1, (3 * n) // 4)]
        est = {
            "value": round(median, 0),
            "low": round(lo, 0),
            "high": round(hi, 0),
            "samples": n,
            "spread": round(hi - lo, 0),
            "age_s": 0.0,
            "stale": False,
        }
        self.last[field] = dict(est, _at=now)
        return est


def select(radar: dict | None, csi: dict | None, distance_m: float | None,
           smoother: "Smoother | None" = None) -> dict:
    r_hr = (radar or {}).get("heart_rate_bpm")
    r_rr = (radar or {}).get("respiration_rpm")
    c_hr = (csi or {}).get("heart_rate_bpm")
    c_rr = (csi or {}).get("breathing_rpm")

    hr, hr_src, hr_why = _pick("heart", r_hr, c_hr, distance_m, RADAR_HEART_RANGE_M)
    rr, rr_src, rr_why = _pick("resp", r_rr, c_rr, distance_m, RADAR_RESP_RANGE_M)

    disagreements = []
    if r_hr is not None and c_hr is not None:
        d = abs(r_hr - c_hr)
        if d >= HEART_DISAGREE_BPM:
            disagreements.append(
                f"heart rate: radar {r_hr:.0f} vs Wi-Fi {c_hr:.0f} bpm ({d:.0f} apart)"
            )
    if r_rr is not None and c_rr is not None:
        d = abs(r_rr - c_rr)
        if d >= RESP_DISAGREE_RPM:
            disagreements.append(
                f"breathing: radar {r_rr:.0f} vs Wi-Fi {c_rr:.0f} /min ({d:.0f} apart)"
            )

    # One instrument finding a heartbeat while failing to find breathing is
    # backwards: breathing is a chest excursion of centimetres, a heartbeat is
    # fractions of a millimetre. Worth surfacing, because it usually means the
    # cardiac estimate has locked onto something that is not a heartbeat.
    suspect = None
    if c_hr is not None and c_rr is None:
        suspect = ("Wi-Fi reports a heart rate but cannot find breathing, "
                   "which is backwards - breathing is the larger signal")
    elif r_hr is not None and r_rr is None:
        suspect = ("Radar reports a heart rate but cannot find breathing, "
                   "which is backwards - breathing is the larger signal")

    # Smoothed estimate alongside the instantaneous value. This is what to
    # read when a number is wanted rather than a measurement: a median over the
    # last 20 s with an interquartile band, so the spread is visible instead of
    # being hidden behind a decimal point.
    estimate = {}
    if smoother is not None:
        smoother.add("heart", hr)
        smoother.add("resp", rr)
        est_hr = smoother.estimate("heart")
        est_rr = smoother.estimate("resp")
        if est_hr:
            estimate["heart_rate_bpm"] = est_hr
        if est_rr:
            estimate["respiration_rpm"] = est_rr

    return {
        "estimate": estimate,
        "heart_rate_bpm": None if hr is None else round(hr, 1),
        "heart_source": hr_src,
        "heart_reason": hr_why,
        "respiration_rpm": None if rr is None else round(rr, 1),
        "respiration_source": rr_src,
        "respiration_reason": rr_why,
        "disagreements": disagreements,
        "agree": not disagreements,
        "suspect": suspect,
        "radar": {"heart_rate_bpm": r_hr, "respiration_rpm": r_rr},
        "wifi_csi": {"heart_rate_bpm": c_hr, "respiration_rpm": c_rr},
    }
