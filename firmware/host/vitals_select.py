"""Choose which instrument to believe, and say when they disagree.

Neither instrument is validated against a reference device, so this is a
routing rule grounded in physics, not an accuracy ranking.

  - Radar is a 60 GHz beam with range gating. At 5 mm wavelength a
    sub-millimetre chest movement is a large fraction of a cycle. Range gating supports target selection; accuracy still requires
    reference validation.
  - CSI is a 2.4 GHz whole-path measurement with one antenna and no spatial
    selectivity at all. Any motion anywhere along the link lands in the same
    number. A usable signal is not proof of longer vital-sign range, and it
    cannot tell you that the change it saw was the person.

So: radar inside its stated range, CSI beyond it, and an explicit disagreement
flag whenever both are present and differ enough to matter.
"""

from __future__ import annotations

import math
import time

# From the bring-up brief: vital signs need a nearly stationary subject within
# ~1.5 m for heart rate and ~2 m for respiration. The bench dashboard uses
# the conservative shared 1.5 m boundary when choosing radar over CSI.
RADAR_HEART_RANGE_M = 1.5
RADAR_RESP_RANGE_M = 1.5

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
    if radar_val is not None and distance_m is None:
        return radar_val, "radar", "range unknown - treat with caution"
    if radar_val is not None:
        # Out of range but the only reading there is. Hand it back labelled,
        # rather than dropping it silently.
        return radar_val, "radar", f"out of range ({distance_m:.2f} m) - treat with caution"
    return None, None, "neither instrument produced a reading"


# Display smoothing is descriptive; it does not establish accuracy.
SMOOTH_WINDOW_S = 8.0
UPDATE_INTERVAL_S = 4.0
MIN_SMOOTH_SAMPLES = 3
MAX_READING_AGE_S = 3.0
JUMP_LIMIT = {"heart": 15.0, "resp": 5.0}


def _positive(value):
    return value if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None


class Smoother:
    """Publish a quality-weighted rate every four seconds from fresh samples."""

    def __init__(self) -> None:
        self.series = {}
        self.sources = {}
        self.published = {}

    def add(self, field, value, now=None, source=None, quality=1.0):
        now = time.monotonic() if now is None else now
        value = _positive(value)
        quality = max(0.0, min(1.0, float(quality)))
        if value is None or quality == 0 or self.sources.get(field) != source:
            self.series.pop(field, None)
            self.published.pop(field, None)
        self.sources[field] = source
        if value is None or quality == 0:
            return
        s = self.series.setdefault(field, [])
        if s and now == s[-1][0]:
            return  # another dashboard refresh is not another observation
        if s and now < s[-1][0]:
            s = []
            self.published.pop(field, None)
        self.series[field] = [(t, v, q) for t, v, q in s if now-t <= SMOOTH_WINDOW_S] + [(now, value, quality)]

    def estimate(self, field, now=None):
        now = time.monotonic() if now is None else now
        s = [(t, v, q) for t, v, q in self.series.get(field, []) if 0 <= now-t <= SMOOTH_WINDOW_S]
        self.series[field] = s
        if len(s) < MIN_SMOOTH_SAMPLES or now-s[-1][0] > MAX_READING_AGE_S:
            return None
        published = self.published.get(field)
        if published is None or now-published["updated_at"] >= UPDATE_INTERVAL_S:
            recent = [(t, v, q) for t, v, q in s if now-t <= UPDATE_INTERVAL_S]
            if len(recent) < MIN_SMOOTH_SAMPLES:
                return None if published is None else self._result(published, s, now)
            candidate = sum(v*q for _, v, q in recent) / sum(q for _, _, q in recent)
            if published is not None:
                old = published["value"]
                limit = JUMP_LIMIT.get(field, 10.0)
                if abs(candidate-old) > limit:
                    changed = [(t, v, q) for t, v, q in recent if abs(v-old) > limit]
                    confirmed = (len(changed) >= 3 and changed[-1][0]-changed[0][0] >= 1.5
                                 and sum(q for _, _, q in changed) >= 1.5)
                    if not confirmed:
                        inliers = [(t, v, q) for t, v, q in recent if abs(v-old) <= limit]
                        if not inliers:
                            return None
                        candidate = sum(v*q for _, v, q in inliers) / sum(q for _, _, q in inliers)
                candidate = old + 0.35*(candidate-old)
            values = sorted(v for _, v, _ in recent)
            lo, hi = values[len(values)//4], values[min(len(values)-1, 3*len(values)//4)]
            published = {"value": candidate, "low": lo, "high": hi, "updated_at": now}
            self.published[field] = published
        return self._result(published, s, now)

    @staticmethod
    def _result(published, samples, now):
        return {"value": round(published["value"], 0),
                "low": round(published["low"], 0), "high": round(published["high"], 0),
                "samples": len(samples), "spread": round(published["high"]-published["low"], 0),
                "age_s": round(now-samples[-1][0], 1), "stale": False,
                "updated_at_s": round(published["updated_at"], 1),
                "weight_basis": "heuristic_sensor_quality"}


def select(radar: dict | None, csi: dict | None, distance_m: float | None,
           smoother: "Smoother | None" = None, *,
           sample_times: dict | None = None, now: float | None = None,
           health: dict | None = None) -> dict:
    r_hr = _positive((radar or {}).get("heart_rate_bpm"))
    r_rr = _positive((radar or {}).get("respiration_rpm"))
    c_hr = _positive((csi or {}).get("heart_rate_bpm"))
    c_rr = _positive((csi or {}).get("breathing_rpm"))

    distance_m = _positive(distance_m)
    now = time.monotonic() if now is None else now
    hr, hr_src, hr_why = _pick("heart", r_hr, c_hr, distance_m, RADAR_HEART_RANGE_M)
    rr, rr_src, rr_why = _pick("resp", r_rr, c_rr, distance_m, RADAR_RESP_RANGE_M)

    heart_agree = None if r_hr is None or c_hr is None else abs(r_hr-c_hr) < HEART_DISAGREE_BPM
    respiration_agree = None if r_rr is None or c_rr is None else abs(r_rr-c_rr) < RESP_DISAGREE_RPM
    if sample_times is not None:
        def aligned(field):
            a = sample_times.get(("radar", field))
            b = sample_times.get(("wifi_csi", field))
            return a is not None and b is not None and abs(a-b) <= 1.0
        if not aligned("heart"):
            heart_agree = None
        if not aligned("resp"):
            respiration_agree = None
    comparisons = [v for v in (heart_agree, respiration_agree) if v is not None]
    disagreements = []
    if heart_agree is False:
        d = abs(r_hr - c_hr)
        if d >= HEART_DISAGREE_BPM:
            disagreements.append(
                f"heart rate: radar {r_hr:.0f} vs Wi-Fi {c_hr:.0f} bpm ({d:.0f} apart)"
            )
    if respiration_agree is False:
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

    # Weight distinct observations by engineering quality factors. Breathing
    # supports the plausibility of a heart estimate but cannot calculate BPM.
    estimate = {}
    if smoother is not None:
        times = sample_times or {}
        def quality(source, field, agreement):
            if source is None:
                return 0.0
            if source == "radar":
                rate = (health or {}).get("radar", {}).get("hz")
                weight = min(1.0, rate / 8.0) if rate is not None else 1.0
                limit = RADAR_HEART_RANGE_M if field == "heart" else RADAR_RESP_RANGE_M
                if distance_m is None or distance_m > limit:
                    weight *= 0.4
            else:
                rate = (health or {}).get("csi", {}).get("hz")
                weight = min(1.0, rate / 25.0) if rate is not None else 1.0
                key = "heart_confidence" if field == "heart" else "breathing_confidence"
                weight *= _positive((csi or {}).get(key)) or 0.4
                weight *= 0.4  # one antenna cannot select a person spatially
            # CSI is secondary on this bench; its disagreement must not
            # suppress an in-range radar reading. Keep the disagreement in
            # metadata for later validation against a reference instrument.
            if agreement is False and source == "wifi_csi":
                weight *= 0.35
            return max(0.0, min(1.0, weight))

        smoother.add("resp", rr, now=times.get((rr_src, "resp"), now), source=rr_src,
                     quality=quality(rr_src, "resp", respiration_agree))
        est_rr = smoother.estimate("resp", now=now)
        same_source_breath = (hr_src == rr_src and rr is not None and
                              (not times or abs(times.get((hr_src, "heart"), now)
                                                - times.get((rr_src, "resp"), now)) <= 2.0))
        heart_quality = quality(hr_src, "heart", heart_agree) if same_source_breath else 0.0
        if est_rr is not None and rr is not None and abs(rr-est_rr["value"]) > JUMP_LIMIT["resp"]:
            heart_quality *= 0.25
        smoother.add("heart", hr, now=times.get((hr_src, "heart"), now),
                     source=hr_src, quality=heart_quality)
        est_hr = smoother.estimate("heart", now=now)
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
        "agree": all(comparisons) if comparisons else None,
        "heart_agree": heart_agree,
        "respiration_agree": respiration_agree,
        "suspect": suspect,
        "radar": {"heart_rate_bpm": r_hr, "respiration_rpm": r_rr},
        "wifi_csi": {"heart_rate_bpm": c_hr, "respiration_rpm": c_rr},
    }
