"""Core-temperature estimation from MLX90640 pixels.

Every correction here is physical and each one is reported separately, so the
final number can be audited rather than trusted.

MLX90640 datasheet figures used:
  accuracy      +/-1.0 C typical (target 20-40 C, ambient 15-35 C)
  NETD          0.1 K RMS at 1 Hz
  field of view 55 x 35 degrees over 32 x 24 pixels
  emissivity    assumed 1.0 by the driver unless corrected

Correction chain, in order:

1. EMISSIVITY. The driver reports a temperature computed as if the target were
   a perfect blackbody. Skin is about 0.98 and reflects the rest of the room:

       sigma*T_meas^4 = eps*sigma*T_obj^4 + (1-eps)*sigma*T_refl^4

   Inverting for T_obj, with the room as T_refl, adds roughly +0.25 C for skin
   at 35 C in a 22 C room. Small, but free and always in the same direction.

2. FILL FACTOR. This is the large one and it is purely geometric. A pixel
   subtends a fixed angle, so its footprint grows linearly with distance:

       IFOV_h = 55/32 = 1.72 deg,  IFOV_v = 35/24 = 1.46 deg
       footprint = 2 * d * tan(IFOV/2)

   giving about 3.0 x 2.5 cm at 1 m and 9.0 x 7.6 cm at 3 m. A forehead is
   roughly 5 x 4 cm = 20 cm^2. Once the pixel is larger than the forehead, the
   reading is an area-weighted radiance mix of skin and whatever is behind it:

       T_meas^4 = f*T_skin^4 + (1-f)*T_bg^4

   Inverting for T_skin recovers several degrees at range. Because radiance
   goes as the fourth power the correction is non-linear, and it is why an
   uncorrected reading falls steadily as someone walks away.

3. SKIN TO CORE. This is the step that cannot be derived, only calibrated.
   Forehead skin sits roughly 3-4 C below core, and the gap moves with ambient
   temperature, perfusion, sweat and whether the person just came indoors.
   A default ambient-compensated offset is applied, and a calibration hook
   lets a real thermometer reading pin it down for one setup.

UNCERTAINTY. The sensor's own +/-1.0 C is already +/-1.8 F, so no amount of
processing produces a clinical instrument here. A clinical thermometer is about
+/-0.4 F. The budget is computed per reading and reported alongside.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SKIN_EMISSIVITY = 0.98

IFOV_H_DEG = 55.0 / 32.0
IFOV_V_DEG = 35.0 / 24.0

# Adult forehead patch usable for thermometry, in metres.
FOREHEAD_W_M = 0.05
FOREHEAD_H_M = 0.04

# Skin-to-core at a reference ambient, and how the gap widens as the room
# cools. Literature values for forehead sit around 3-4 C at 20-25 C ambient.
# These are defaults to be calibrated, not constants to be trusted.
DEFAULT_SKIN_TO_CORE_C = 3.4
REFERENCE_AMBIENT_C = 22.0
AMBIENT_SLOPE = 0.13  # extra C of gap per C the room is below reference

# Uncertainty contributions, 1-sigma, in C.
# Below this fill fraction the unmixing in step 2 stops being a correction and
# starts being an extrapolation. Inverting a fourth-power mix amplifies every
# error in the assumed forehead size and background temperature, and it runs
# away fast: at 29% fill the same input yields 142 F. No number is reported
# below the gate.
MIN_FILL_FOR_CORE = 0.60

U_SENSOR_C = 1.0        # datasheet accuracy
U_EMISSIVITY_C = 0.3    # skin emissivity 0.95-0.99
U_SKIN_TO_CORE_C = 1.2  # biological and environmental spread

C_TO_K = 273.15


def c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def pixel_footprint_m(distance_m: float) -> tuple[float, float]:
    w = 2.0 * distance_m * math.tan(math.radians(IFOV_H_DEG / 2))
    h = 2.0 * distance_m * math.tan(math.radians(IFOV_V_DEG / 2))
    return w, h


def emissivity_correct(t_meas_c: float, t_refl_c: float, eps: float = SKIN_EMISSIVITY) -> float:
    """Undo the driver's blackbody assumption. Stefan-Boltzmann, in kelvin."""
    tm = t_meas_c + C_TO_K
    tr = t_refl_c + C_TO_K
    inner = (tm**4 - (1.0 - eps) * tr**4) / eps
    if inner <= 0:
        return t_meas_c
    return inner**0.25 - C_TO_K


def fill_factor(distance_m: float) -> float:
    """Fraction of one pixel covered by forehead skin. Capped at 1."""
    pw, ph = pixel_footprint_m(distance_m)
    pixel_area = pw * ph
    if pixel_area <= 0:
        return 1.0
    return min(1.0, (FOREHEAD_W_M * FOREHEAD_H_M) / pixel_area)


def unmix(t_meas_c: float, t_bg_c: float, f: float) -> float:
    """Recover skin temperature from a radiance-mixed pixel."""
    if f >= 0.999:
        return t_meas_c
    tm = t_meas_c + C_TO_K
    tb = t_bg_c + C_TO_K
    inner = (tm**4 - (1.0 - f) * tb**4) / f
    if inner <= 0:
        return t_meas_c
    return inner**0.25 - C_TO_K


@dataclass
class Calibration:
    """Offset fitted against a real thermometer, for one setup."""

    skin_to_core_c: float = DEFAULT_SKIN_TO_CORE_C
    samples: int = 0
    calibrated: bool = False

    def fit(self, skin_c: float, reference_core_c: float) -> None:
        obs = reference_core_c - skin_c
        if self.samples == 0:
            self.skin_to_core_c = obs
        else:
            # Running mean; a handful of readings is plenty for one geometry.
            self.skin_to_core_c += (obs - self.skin_to_core_c) / (self.samples + 1)
        self.samples += 1
        self.calibrated = True


def usable_range_m() -> float:
    """Greatest distance at which a forehead still fills MIN_FILL_FOR_CORE."""
    area = FOREHEAD_W_M * FOREHEAD_H_M / MIN_FILL_FOR_CORE
    k = 4.0 * math.tan(math.radians(IFOV_H_DEG / 2)) * math.tan(math.radians(IFOV_V_DEG / 2))
    return math.sqrt(area / k)


def estimate(
    peak_head_c: float,
    ambient_c: float,
    distance_m: float | None,
    cal: Calibration,
    background_c: float | None = None,
) -> dict:
    steps = []

    # The surroundings inside a pixel are hair, neck and shoulders, all warmer
    # than the room. Unmixing against room temperature therefore over-corrects.
    # Prefer a measured local background when the caller supplies one.
    bg_c = background_c if background_c is not None else ambient_c

    # 1. emissivity
    t_eps = emissivity_correct(peak_head_c, ambient_c)
    steps.append({
        "step": "emissivity",
        "delta_c": round(t_eps - peak_head_c, 2),
        "note": f"skin eps={SKIN_EMISSIVITY}, room reflection at {ambient_c:.1f} C",
    })

    # 2. fill factor
    if distance_m:
        f = fill_factor(distance_m)
        t_fill = unmix(t_eps, bg_c, f)
        pw, ph = pixel_footprint_m(distance_m)
        steps.append({
            "step": "fill factor",
            "delta_c": round(t_fill - t_eps, 2),
            "note": (f"pixel {pw*100:.1f}x{ph*100:.1f} cm, forehead fills {f*100:.0f}%"
                     f", background {bg_c:.1f} C"),
        })
    else:
        f = 1.0
        t_fill = t_eps
        steps.append({"step": "fill factor", "delta_c": 0.0,
                      "note": "no distance available; assumed pixel is filled"})

    skin_c = t_fill

    # Gate before the core step. An out-of-range reading is refused rather than
    # reported with a wide error bar, because a plausible-looking number with
    # +/-8 F on it still gets read as a temperature.
    if f < MIN_FILL_FOR_CORE:
        return {
            "measured_f": round(c_to_f(peak_head_c), 1),
            "skin_f": round(c_to_f(skin_c), 1),
            "core_f": None,
            "uncertainty_f": None,
            "fill_fraction": round(f, 3),
            "calibrated": cal.calibrated,
            "steps": steps,
            "unavailable": (
                f"too far for thermometry: the forehead fills only {f*100:.0f}% of a "
                f"pixel, and correcting past {MIN_FILL_FOR_CORE*100:.0f}% amplifies "
                f"error faster than it removes bias. Move within "
                f"{usable_range_m():.1f} m."
            ),
        }

    # 3. skin to core
    gap = cal.skin_to_core_c + AMBIENT_SLOPE * (REFERENCE_AMBIENT_C - ambient_c)
    core_c = skin_c + gap
    steps.append({
        "step": "skin to core",
        "delta_c": round(gap, 2),
        "note": (f"calibrated on {cal.samples} reading(s)" if cal.calibrated
                 else f"uncalibrated default, ambient-adjusted from {REFERENCE_AMBIENT_C:.0f} C"),
    })

    # Uncertainty. Fill-factor error grows as the correction grows, because a
    # bigger correction multiplies any error in the assumed forehead size.
    u_fill = 0.2 + 2.5 * (1.0 - f)
    u_core = U_SKIN_TO_CORE_C * (0.35 if cal.calibrated else 1.0)
    u_total_c = math.sqrt(
        U_SENSOR_C**2 + U_EMISSIVITY_C**2 + u_fill**2 + u_core**2
    )

    return {
        "measured_f": round(c_to_f(peak_head_c), 1),
        "skin_f": round(c_to_f(skin_c), 1),
        "core_f": round(c_to_f(core_c), 1),
        "uncertainty_f": round(u_total_c * 9 / 5, 1),
        "fill_fraction": round(f, 3),
        "calibrated": cal.calibrated,
        "steps": steps,
        "budget_c": {
            "sensor": U_SENSOR_C,
            "emissivity": U_EMISSIVITY_C,
            "fill_factor": round(u_fill, 2),
            "skin_to_core": round(u_core, 2),
            "total": round(u_total_c, 2),
        },
    }
