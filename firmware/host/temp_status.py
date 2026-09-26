"""Is this reading unusual? Answered two ways, because one of them works.

ABSOLUTE, against population norms. This mostly cannot answer the question and
says so. The estimate carries about +/-2.1 F while the whole normal range spans
roughly 97-99 F, so a reading of 98.6 F is consistent with a true 96.5 or a
true 100.7. A verdict is only returned when the reading clears a threshold by
more than its own uncertainty; otherwise the honest output is that the
measurement cannot distinguish.

RELATIVE, against this person's own history. This works far better, for a
reason worth stating plainly: **systematic error cancels in a difference**.
The dominant term in the budget is the sensor's +/-1.0 C accuracy, which is
largely a fixed bias for a given sensor, mounting and distance - it shifts
every reading the same way, so it disappears when comparing today's reading to
the same person's usual reading through the same setup. Random noise then falls
as more samples accumulate.

So a 3 F rise against someone's own baseline is detectable even when the
absolute number is off by 2 F. That is the useful signal here.

Nothing in this module diagnoses anything. It reports whether a measurement is
unusual for this person and whether the instrument can tell - a caregiver
observation, not a clinical finding.
"""

from __future__ import annotations

import math
import time

import confidence
from dataclasses import dataclass, field

# Population reference points, degrees F. Used only for the absolute check.
TYPICAL_LOW_F = 97.0
TYPICAL_HIGH_F = 99.0
FEVER_F = 100.4
HYPOTHERMIA_F = 95.0

# A baseline is not meaningful until it has seen enough of the person.
MIN_BASELINE_SAMPLES = 40
BASELINE_WINDOW_S = 7 * 24 * 3600


@dataclass
class Baseline:
    """Rolling record of one person's readings through one setup."""

    samples: list[tuple[float, float]] = field(default_factory=list)

    def add(self, value_f: float, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        self.samples.append((now, value_f))
        cutoff = now - BASELINE_WINDOW_S
        self.samples = [(t, v) for t, v in self.samples if t >= cutoff]

    @property
    def ready(self) -> bool:
        return len(self.samples) >= MIN_BASELINE_SAMPLES

    def stats(self) -> tuple[float, float] | None:
        if not self.ready:
            return None
        vals = sorted(v for _, v in self.samples)
        n = len(vals)
        median = vals[n // 2]
        # Median absolute deviation, scaled to a standard-deviation equivalent.
        # Robust against the occasional bad frame in a way a mean is not.
        mad = sorted(abs(v - median) for v in vals)[n // 2]
        return median, max(mad * 1.4826, 0.3)

    def to_dict(self) -> dict:
        return {"samples": self.samples[-2000:]}

    def load(self, path) -> None:
        import json
        import os
        if not os.path.exists(path):
            return
        try:
            with open(path) as fh:
                self.samples = [tuple(x) for x in json.load(fh).get("samples", [])]
        except Exception:
            pass

    def save(self, path) -> None:
        import json
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh)


def assess(core_f: float | None, uncertainty_f: float | None,
           baseline: Baseline) -> dict:
    if core_f is None:
        return {"state": "no reading", "detail": "no usable temperature",
                "can_tell": False}

    u = uncertainty_f or 2.0

    # --- absolute ---------------------------------------------------------
    if core_f - u > FEVER_F:
        absolute = {"verdict": "above typical range",
                    "detail": f"{core_f:.1f} F is above {FEVER_F} F even allowing "
                              f"for the full +/-{u:.1f} F uncertainty"}
    elif core_f + u < HYPOTHERMIA_F:
        absolute = {"verdict": "below typical range",
                    "detail": f"{core_f:.1f} F is below {HYPOTHERMIA_F} F even "
                              f"allowing for the full +/-{u:.1f} F uncertainty"}
    else:
        lo, hi = core_f - u, core_f + u
        absolute = {"verdict": "cannot distinguish",
                    "detail": f"true value is somewhere in {lo:.1f}-{hi:.1f} F, "
                              f"which overlaps the normal range"}

    # --- relative ---------------------------------------------------------
    st = baseline.stats()
    if st is None:
        relative = {"verdict": "building baseline",
                    "detail": f"{len(baseline.samples)} of {MIN_BASELINE_SAMPLES} "
                              "readings collected for this person"}
        state = absolute["verdict"]
        can_tell = absolute["verdict"] != "cannot distinguish"
    else:
        median, spread = st
        delta = core_f - median
        z = delta / spread

        # Derive the verdict from the same percentage that gets reported.
        # Thresholding on raw z separately produced readings labelled "usual
        # for this person" while carrying 86% unusualness - both correct by
        # their own formula, and plainly contradictory to anyone reading them.
        pct, _why = confidence.unusualness_pct(z, len(baseline.samples))
        if pct < 80.0:
            verdict = "usual for this person"
        elif pct < 95.0:
            verdict = "mildly unusual"
        else:
            verdict = "unusual for this person"
        relative = {
            "verdict": verdict,
            "unusualness_pct": pct,
            "detail": (f"{delta:+.1f} F from a usual {median:.1f} F; a gap this "
                       f"large shows up in about {100-pct:.0f}% of readings"),
        }
        relative["delta_f"] = round(delta, 1)
        relative["baseline_f"] = round(median, 1)
        relative["spread_f"] = round(spread, 1)

        # Prefer the relative answer: it cancels the fixed sensor bias that
        # dominates the absolute uncertainty.
        state = relative["verdict"]
        can_tell = True

    return {"state": state, "absolute": absolute, "relative": relative,
            "can_tell": can_tell,
            "note": "an observation about this reading, not a medical assessment"}
