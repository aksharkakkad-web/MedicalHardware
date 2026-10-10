"""Breathing and heart-rate estimation from CSI amplitude. Runs on the host.

Method follows the one ruvnet/ruview arrived at in its esp32-csi-node edge DSP:
biquad bandpass into breathing (0.1-0.5 Hz) and cardiac (0.8-2.0 Hz) bands,
then autocorrelation for the rate.

The important detail is *why* they use autocorrelation with explicit harmonic
rejection rather than zero-crossing. Their own source records the failure: a
zero-crossing estimator "locked onto breathing harmonics - a 0.25 Hz breathing
fundamental puts its 3rd harmonic at ~0.74 Hz, approximately 44 BPM", so it sat
at a confident, plausible, entirely wrong ~45 BPM. That is the same class of
failure as this project's radar reporting 119 bpm off a desk, and it is the
reason every candidate lag near a breathing harmonic is rejected below.

Nothing here is validated. RuView's own ADR-293 states that for vitals,
"MEASURED is currently unreachable" - there is no reference-sensor ground truth
in that project either. Producing a trustworthy number needs a chest strap or
pulse oximeter recorded alongside. Until then these are unvalidated estimates
and must be labelled as such wherever they surface.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

# Analysis bands. Breathing 6-30 breaths/min, cardiac 48-120 bpm.
BREATH_LO_HZ, BREATH_HI_HZ = 0.10, 0.50
HEART_LO_HZ, HEART_HI_HZ = 0.80, 2.00

# Vitals need a long observation. Breathing at 0.1 Hz is a 10 s period, so a
# 30 s window holds only three cycles - shorter than this and the estimate is
# not meaningfully better than a guess.
BREATH_WINDOW_S = 30.0
HEART_WINDOW_S = 20.0

# Decimation rate per band. Breathing is slow and 10 Hz is ample. Cardiac is
# not: at 10 Hz a 1.2 Hz pulse is only 8.3 samples per cycle, so adjacent
# autocorrelation lags land 8 bpm apart and the estimator cannot resolve a
# rate even when the signal is clean. Keep the cardiac band near the native
# capture rate.
BREATH_TARGET_HZ = 10.0
HEART_TARGET_HZ = 25.0
N_SUBCARRIERS_USED = 6

# Fractional half-width of the breathing-harmonic guard band. See the rejection
# loop for why this is narrow.
HARMONIC_GUARD = 0.03


@dataclass
class VitalEstimate:
    """``rate`` is None whenever the estimate is not trustworthy.

    There is no "best guess" fallback. An absent value is reported as absent,
    which is the same rule the radar and ambient paths follow.
    """

    rate: float | None = None
    confidence: float = 0.0
    reason: str = "no data"


class _Biquad:
    """2nd-order Butterworth bandpass, direct form I."""

    def __init__(self, fs: float, lo: float, hi: float) -> None:
        centre = math.sqrt(lo * hi)
        bw = max(hi - lo, 1e-6)
        w0 = 2.0 * math.pi * centre / fs
        q = centre / bw
        alpha = math.sin(w0) / (2.0 * q)
        cos_w0 = math.cos(w0)

        b0, b1, b2 = alpha, 0.0, -alpha
        a0, a1, a2 = 1.0 + alpha, -2.0 * cos_w0, 1.0 - alpha
        self.b = (b0 / a0, b1 / a0, b2 / a0)
        self.a = (a1 / a0, a2 / a0)

    def apply_twice(self, xs: list[float]) -> list[float]:
        """Cascade the section for a steeper skirt.

        One 2nd-order section leaks far too much breathing energy into the
        cardiac band: on a synthetic 15 brpm + 72 bpm signal the single-section
        version returned a confident 120 bpm, having locked onto the breathing
        residual at the band edge.
        """
        return self.apply(self.apply(xs))

    def apply(self, xs: list[float]) -> list[float]:
        b0, b1, b2 = self.b
        a1, a2 = self.a
        x1 = x2 = y1 = y2 = 0.0
        out = []
        for x in xs:
            y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            out.append(y)
            x2, x1 = x1, x
            y2, y1 = y1, y
        return out


def _detrend(xs: list[float]) -> list[float]:
    n = len(xs)
    if n < 2:
        return [0.0] * n
    mean_i = (n - 1) / 2.0
    mean_x = sum(xs) / n
    num = sum((i - mean_i) * (x - mean_x) for i, x in enumerate(xs))
    den = sum((i - mean_i) ** 2 for i in range(n)) or 1.0
    slope = num / den
    return [x - (mean_x + slope * (i - mean_i)) for i, x in enumerate(xs)]


def _autocorr_rate(
    xs: list[float],
    fs: float,
    bpm_lo: float,
    bpm_hi: float,
    reject_hz: float | None = None,
) -> tuple[float | None, float]:
    """Dominant rate in BPM within the band, by autocorrelation peak.

    ``reject_hz`` is a breathing fundamental whose harmonics are excluded. This
    is what stops the cardiac band locking onto the 3rd harmonic of breathing
    and reporting a confident ~45 bpm.
    """
    n = len(xs)
    if n < 32 or fs <= 0:
        return None, 0.0

    lag_min = max(1, int(fs * 60.0 / bpm_hi))
    lag_max = min(n - 1, int(fs * 60.0 / bpm_lo))
    if lag_max <= lag_min:
        return None, 0.0

    energy = sum(x * x for x in xs)
    if energy <= 1e-12:
        return None, 0.0

    # Compute the whole curve first: a genuine period shows up as a local
    # maximum, whereas leakage from a slower rhythm shows up as a monotonic
    # decay from the shortest lag. Taking the largest value alone cannot tell
    # those apart, which is how the cardiac band locked onto breathing.
    curve = []
    for lag in range(lag_min, lag_max + 1):
        acc = 0.0
        for i in range(n - lag):
            acc += xs[i] * xs[i + lag]
        curve.append(acc / energy)

    best_lag, best_val = None, 0.0
    for j in range(1, len(curve) - 1):
        val = curve[j]
        if not (val > curve[j - 1] and val >= curve[j + 1]):
            continue  # not a peak
        lag = lag_min + j
        if reject_hz and reject_hz > 0:
            f = fs / lag
            # Reject candidates sitting on a breathing harmonic. The window has
            # to be narrow: at 0.25 Hz breathing the harmonics k=4,5,6 fall on
            # 60, 75 and 90 bpm, so a wide guard band blankets the entire
            # cardiac range and rejects every real heart rate along with the
            # artefacts. Measured at 8% it rejected a clean 72 bpm; 3% keeps
            # 72 while still catching a candidate sitting on 75.
            if any(
                abs(f - k * reject_hz) < HARMONIC_GUARD * k * reject_hz
                for k in range(2, 9)
            ):
                continue
        if val > best_val:
            best_val, best_lag = val, lag

    # A weak peak means no periodicity worth reporting.
    if best_lag is None or best_val < 0.30:
        return None, best_val

    # Refine between lags. Autocorrelation lags are integers, so without this
    # the reported rate snaps to coarse steps - about 8 bpm apart in the
    # cardiac band even at 25 Hz.
    j = best_lag - lag_min
    lag_ref = float(best_lag)
    if 0 < j < len(curve) - 1:
        a, b, c = curve[j - 1], curve[j], curve[j + 1]
        denom = a - 2.0 * b + c
        if abs(denom) > 1e-12:
            lag_ref = best_lag + 0.5 * (a - c) / denom

    return fs * 60.0 / lag_ref, best_val


class VitalsEstimator:
    """Rolling CSI buffer plus band estimates. Feed it amplitude vectors."""

    def __init__(self) -> None:
        self.samples: list[tuple[float, list[float]]] = []
        self._last = (VitalEstimate(), VitalEstimate())
        self._last_run = -math.inf
        self._last_received_at = None

    def add(self, t: float, amps: list[float]) -> None:
        if self.samples and (t <= self.samples[-1][0] or t-self.samples[-1][0] > 0.5):
            self.samples = []
            self._last = (VitalEstimate(reason="collecting after gap"), VitalEstimate(reason="collecting after gap"))
            self._last_run = -math.inf
        self._last_received_at = time.monotonic()
        cutoff = t - (BREATH_WINDOW_S + 5.0)
        self.samples = [(ts, a) for ts, a in self.samples if ts >= cutoff] + [(t, amps)]

    def _series(self, window_s: float, target_hz: float) -> tuple[list[list[float]], float]:
        """Decimate to ``target_hz`` and return per-subcarrier series."""
        if not self.samples:
            return [], 0.0
        t_end = self.samples[-1][0]
        t_start = t_end - window_s
        rows = [(t, a) for t, a in self.samples if t >= t_start]
        if len(rows) < 32 or rows[-1][0]-rows[0][0] < window_s-1.0/target_hz:
            return [], 0.0

        step = 1.0 / target_hz
        n_bins = int(window_s / step)
        n_sub = min(len(rows[0][1]), 64)
        bins: list[list[float]] = [[] for _ in range(n_bins)]
        for t, amps in rows:
            idx = int((t - t_start) / step)
            if 0 <= idx < n_bins:
                bins[idx].append(amps)

        series = [[] for _ in range(n_sub)]
        last = None
        for b in bins:
            if b:
                last = [sum(a[k] for a in b) / len(b) for k in range(n_sub)]
            if last is None:
                continue
            for k in range(n_sub):
                series[k].append(last[k])

        actual_len = len(series[0]) if series and series[0] else 0
        if actual_len < 32:
            return [], 0.0
        return series, target_hz

    def estimate(self) -> tuple[VitalEstimate, VitalEstimate]:
        # Rate-limit: this is O(lags x samples) in pure Python.
        now = time.monotonic()
        if self._last_received_at is None or now-self._last_received_at > 3.0:
            self._last = (VitalEstimate(reason="CSI stream unavailable"), VitalEstimate(reason="CSI stream unavailable"))
            return self._last
        if now - self._last_run < 1.0:
            return self._last
        self._last_run = now

        breath = VitalEstimate(reason="collecting")
        heart = VitalEstimate(reason="collecting")

        series, fs = self._series(BREATH_WINDOW_S, BREATH_TARGET_HZ)
        if not series:
            self._last = (breath, heart)
            return self._last

        # Chest motion shows up strongly on some subcarriers and not others,
        # so rank by variance and use only the most responsive.
        ranked = sorted(
            range(len(series)),
            key=lambda k: -_variance(series[k]),
        )[:N_SUBCARRIERS_USED]

        breath_rates, breath_confs = [], []
        for k in ranked:
            xs = _Biquad(fs, BREATH_LO_HZ, BREATH_HI_HZ).apply_twice(_detrend(series[k]))
            rate, conf = _autocorr_rate(xs, fs, BREATH_LO_HZ * 60, BREATH_HI_HZ * 60)
            if rate is not None:
                breath_rates.append(rate)
                breath_confs.append(conf)

        breath_hz = None
        if len(breath_rates) >= 3:
            breath_rates.sort()
            med = breath_rates[len(breath_rates) // 2]
            # Agreement across independent subcarriers is the confidence signal.
            agree = [r for r in breath_rates if abs(r - med) < 0.15 * med]
            if len(agree) >= 3:
                breath = VitalEstimate(
                    rate=sum(agree) / len(agree),
                    confidence=min(1.0, len(agree) / len(breath_rates)),
                    reason="ok",
                )
                breath_hz = breath.rate / 60.0
            else:
                breath = VitalEstimate(reason="subcarriers disagree")
        else:
            breath = VitalEstimate(reason="no periodicity in breathing band")

        # Cardiac, with breathing harmonics excluded.
        hseries, hfs = self._series(HEART_WINDOW_S, HEART_TARGET_HZ)
        if hseries:
            hranked = sorted(range(len(hseries)), key=lambda k: -_variance(hseries[k]))[
                :N_SUBCARRIERS_USED
            ]
            hrates = []
            for k in hranked:
                xs = _Biquad(hfs, HEART_LO_HZ, HEART_HI_HZ).apply_twice(_detrend(hseries[k]))
                rate, conf = _autocorr_rate(
                    xs, hfs, HEART_LO_HZ * 60, HEART_HI_HZ * 60, reject_hz=breath_hz
                )
                if rate is not None:
                    hrates.append(rate)
            if len(hrates) >= 4:
                hrates.sort()
                med = hrates[len(hrates) // 2]
                agree = [r for r in hrates if abs(r - med) < 0.12 * med]
                # Cardiac is far weaker than breathing in CSI, so demand
                # agreement from most of the selected subcarriers, not a bare
                # majority.
                if len(agree) >= max(4, int(0.7 * len(hrates))):
                    heart = VitalEstimate(
                        rate=sum(agree) / len(agree),
                        confidence=len(agree) / len(hrates),
                        reason="ok",
                    )
                else:
                    heart = VitalEstimate(reason="subcarriers disagree")
            else:
                heart = VitalEstimate(reason="no periodicity in cardiac band")

        self._last = (breath, heart)
        return self._last


def _variance(xs: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return sum((x - m) ** 2 for x in xs) / n
