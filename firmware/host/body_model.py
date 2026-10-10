"""Body geometry from a 32x24 thermal frame.

Two things the previous version got wrong.

It assumed the whole body was in frame - head taken as the topmost warm row,
base as the bottommost. When someone is close, or seated at a desk, or walking
past the edge, that silently labels a shoulder as a head. Landmarks are now
emitted only where the silhouette's shape actually supports them, each with its
own confidence, and the frame edges are checked so a cut-off body is reported
as cut off.

It also thresholded the whole frame at once, so a radiator or a laptop merged
into the person's blob. Regions are now grown by connectivity and the largest
one is used.

TEMPERATURE. This sensor measures *surface* temperature of whatever faces it -
clothing, hair, exposed skin - at whatever distance, through whatever air is in
between, with no emissivity calibration. Exposed skin typically reads 31-35 C
(88-95 F) against a 37 C (98.6 F) core. The reading is real and is reported
here honestly; it is not body temperature and cannot be used to judge whether
someone is febrile or healthy. See the module note in the dashboard.
"""

from __future__ import annotations

import math

import pose17
import thermometry

COLS = 32
ROWS = 24

# One calibration for the whole process; a fitted offset belongs to a setup,
# not to a frame.
_CALIBRATION = thermometry.Calibration()
_CAL_PATH = __import__("pathlib").Path(__file__).parent / "temp_calibration.json"
_CALIBRATION.load(_CAL_PATH)


def calibrate(skin_c: float, reference_core_c: float,
              ambient_c: float | None = None) -> dict:
    """Pin the skin-to-core offset against a real thermometer.

    The offset belongs to one setup - this sensor, this mounting, this
    distance, this room. It is not a property of the person.
    """
    _CALIBRATION.fit(skin_c, reference_core_c, ambient_c)
    _CALIBRATION.save(_CAL_PATH)
    return _CALIBRATION.to_dict()

# Vertical field of view, from the MLX90640 datasheet, used to convert pixel
# extent into metres once the radar supplies a range.
FOV_V_DEG = 35.0
FOV_H_DEG = 55.0


def _largest_region(mask: list[bool]) -> set[int]:
    """Flood-fill 4-connected regions, return the biggest.

    Thresholding alone merges a person with any other warm object in frame.
    """
    seen = [False] * (COLS * ROWS)
    best: set[int] = set()
    for start in range(COLS * ROWS):
        if not mask[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = True
        region = set()
        while stack:
            i = stack.pop()
            region.add(i)
            r, c = divmod(i, COLS)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                rr, cc = r + dr, c + dc
                if 0 <= rr < ROWS and 0 <= cc < COLS:
                    j = rr * COLS + cc
                    if mask[j] and not seen[j]:
                        seen[j] = True
                        stack.append(j)
        if len(region) > len(best):
            best = region
    return best


def analyse(px: list[float], distance_m: float | None) -> dict | None:
    ordered = sorted(px)
    ambient = ordered[len(ordered) // 2]
    peak = ordered[-1]
    contrast = peak - ambient
    if contrast < 1.8:
        return None

    cut = ambient + contrast * 0.5
    region = _largest_region([v >= cut for v in px])
    if len(region) < 6:
        return None

    rows: dict[int, list[int]] = {}
    for i in region:
        r, c = divmod(i, COLS)
        rows.setdefault(r, []).append(c)
    ys = sorted(rows)
    top, base = ys[0], ys[-1]
    height_px = base - top + 1

    def span(r):
        cs = rows[r]
        return min(cs), max(cs), len(cs)

    # Which edges the silhouette runs into. A body touching an edge is cut off
    # there, so any landmark that would sit beyond it is unknown, not absent.
    all_cols = [c for r in ys for c in rows[r]]
    cut_top = top == 0
    cut_base = base == ROWS - 1
    cut_left = min(all_cols) == 0
    cut_right = max(all_cols) == COLS - 1

    widths = [(r, span(r)[1] - span(r)[0] + 1) for r in ys]
    max_w = max(w for _, w in widths)

    landmarks: dict[str, dict] = {}

    def put(name, col, row, conf, note=""):
        landmarks[name] = {
            "x": round(float(col), 2),
            "y": round(float(row), 2),
            "confidence": round(conf, 2),
            "note": note,
        }

    # --- head -------------------------------------------------------------
    # A head shows as a narrow run above a wider run: the neck. Without that
    # constriction there is no evidence of a head, only a top edge.
    head_row = None
    if not cut_top and height_px >= 5:
        for r in ys[: max(1, int(height_px * 0.6))]:
            w = span(r)[1] - span(r)[0] + 1
            below = [
                span(rr)[1] - span(rr)[0] + 1
                for rr in ys
                if r < rr <= r + max(1, height_px // 6)
            ]
            if below and w <= 0.65 * max(below) and w <= 0.6 * max_w:
                head_row = r
                break
    if head_row is not None:
        hrows = [r for r in ys if r <= head_row]
        hcols = [c for r in hrows for c in rows[r]]
        put("head", sum(hcols) / len(hcols), sum(hrows) / len(hrows), 0.8,
            "narrowing above the shoulders")
    elif cut_top:
        pass  # head is out of frame; say nothing rather than guess
    else:
        top_cols = rows[top]
        put("top_of_mass", sum(top_cols) / len(top_cols), float(top), 0.35,
            "no neck visible; this is the top of the warm region, not a head")

    # --- shoulders --------------------------------------------------------
    upper = [r for r in ys if r <= top + max(1, height_px * 0.55)]
    if upper:
        sh_row = max(upper, key=lambda r: span(r)[1] - span(r)[0])
        lo, hi, _ = span(sh_row)
        wide = (hi - lo + 1) >= 0.7 * max_w
        conf = 0.75 if wide else 0.4
        if cut_left or cut_right:
            conf *= 0.6
        put("shoulder_left", lo, sh_row, conf,
            "cut off at frame edge" if cut_left else "")
        put("shoulder_right", hi, sh_row, conf,
            "cut off at frame edge" if cut_right else "")

    # --- torso ------------------------------------------------------------
    tcols = [c for r in ys for c in rows[r]]
    trows = [r for r in ys for _ in rows[r]]
    put("torso", sum(tcols) / len(tcols), sum(trows) / len(trows), 0.85)

    # --- hips / base ------------------------------------------------------
    if not cut_base:
        bcols = rows[base]
        put("base", sum(bcols) / len(bcols), float(base), 0.6,
            "lowest visible point")

    # --- visibility -------------------------------------------------------
    parts = []
    if cut_top:
        parts.append("cut off at top")
    if cut_base:
        parts.append("cut off at bottom")
    if cut_left or cut_right:
        parts.append("cut off at side")
    if not parts:
        visibility = "fully in frame"
    else:
        visibility = ", ".join(parts)

    # Posture only when there is enough of the body to justify one.
    aspect = height_px / max(1, max_w)
    if cut_top or cut_base:
        posture = "unknown"
        posture_reason = "body extends outside the frame"
    elif aspect >= 1.7:
        posture, posture_reason = "upright", f"height/width {aspect:.1f}"
    elif aspect >= 0.9:
        posture, posture_reason = "seated or turned", f"height/width {aspect:.1f}"
    else:
        posture, posture_reason = "horizontal", f"height/width {aspect:.1f}"

    height_m = None
    if distance_m and not (cut_top or cut_base):
        m_per_px = (2.0 * distance_m * math.tan(math.radians(FOV_V_DEG / 2))) / ROWS
        height_m = round(height_px * m_per_px, 2)

    # --- forehead / head-site temperature --------------------------------
    #
    # A temporal-artery thermometer works by scanning the forehead and keeping
    # the *peak* reading, because any averaging pulls in cooler surroundings.
    # The same logic applies here: take the hottest pixel on the head rather
    # than a mean.
    #
    # What differs from a real thermometer is spatial resolution, and it is not
    # a small difference. One pixel subtends a fixed angle, so its footprint
    # grows with distance:
    #
    #     footprint = 2 * d * tan(FOV/2) / pixels
    #
    # At 1 m that is about 3 cm across; at 3 m about 10 cm. A forehead is
    # roughly 5 cm. Once the footprint exceeds the forehead, every pixel is a
    # blend of skin, hair and background, and the peak reads low - which is why
    # the footprint is reported alongside the temperature rather than buried.
    head_temp = None
    head_rows_t = [r for r in ys if r <= band_of_head] if (band_of_head := top + max(1, int(height_px * 0.18))) else []
    head_px = [px[r * COLS + c] for r in head_rows_t if r in rows for c in rows[r]]
    if head_px and not cut_top:
        peak_head = max(head_px)
        px_w = px_h = None
        quality = "unknown"
        if distance_m:
            px_w = 2.0 * distance_m * math.tan(math.radians(FOV_H_DEG / 2)) / COLS
            px_h = 2.0 * distance_m * math.tan(math.radians(FOV_V_DEG / 2)) / ROWS
            biggest = max(px_w, px_h) * 100.0  # cm
            if biggest <= 3.0:
                quality = "good"
            elif biggest <= 6.0:
                quality = "fair - pixel is about forehead-sized"
            else:
                quality = "poor - each pixel is wider than a forehead"
        # Local background: the ring just outside the head region. Those pixels
        # are hair, neck and shoulders - much warmer than the room - and using
        # room temperature here would over-correct the unmixing.
        ring = []
        head_set = {r * COLS + c for r in head_rows_t if r in rows for c in rows[r]}
        for i in head_set:
            r0, c0 = divmod(i, COLS)
            for dr in (-1, 0, 1):
                for dc in (-2, -1, 1, 2):
                    rr, cc = r0 + dr, c0 + dc
                    j = rr * COLS + cc
                    if 0 <= rr < ROWS and 0 <= cc < COLS and j not in head_set:
                        ring.append(px[j])
        bg_c = sorted(ring)[len(ring) // 2] if ring else ambient

        est = thermometry.estimate(peak_head, ambient, distance_m,
                                   _CALIBRATION, background_c=bg_c)

        head_temp = {
            "estimate": est,
            "background_c": round(bg_c, 1),
            "peak_c": round(peak_head, 1),
            "peak_f": round(peak_head * 9 / 5 + 32, 1),
            "pixels_used": len(head_px),
            "pixel_cm": None if px_w is None else round(max(px_w, px_h) * 100, 1),
            "quality": quality,
            "site": "warmest point on the head",
        }

    # --- surface temperature ---------------------------------------------
    # Warmest pixels within the body region only. The single hottest pixel is
    # noisy, so use the mean of the top few.
    temps = sorted((px[i] for i in region), reverse=True)
    warm = temps[: max(1, len(temps) // 10)]
    surface_c = sum(warm) / len(warm)

    # Name a narrow upper-body site only when the silhouette supports it.
    # Thermal pixels cannot distinguish exposed skin from hair or clothing.
    surface_site = "visible body surface"
    surface_note = "Warm visible surface; skin and material unverified; not core temperature"
    site_values = warm
    if head_row is not None:
        # The generic shoulder landmark searches the upper half and may land
        # on the head. Find the first clear widening below the head instead.
        shoulder_y = next((r for r in ys if r > head_row
                           and span(r)[1] - span(r)[0] + 1 >= 0.7 * max_w), None)
        upper_width = max((span(r)[1] - span(r)[0] + 1 for r in ys if r < head_row),
                          default=0)
        neck_limit = min(0.6 * max_w, 0.65 * upper_width)
        neck_rows = []
        if shoulder_y is not None and upper_width:
            for r in reversed([r for r in ys if top < r < shoulder_y]):
                if span(r)[1] - span(r)[0] + 1 > neck_limit:
                    break
                neck_rows.append(r)
        if neck_rows:
            neck_values = sorted((px[r * COLS + c] for r in neck_rows
                                  for c in rows[r]), reverse=True)
            site_values = neck_values[:max(1, len(neck_values) // 10)]
            surface_site = "neck region"
            surface_note = "Neck-region surface; skin unverified; not core temperature"
        elif head_temp:
            site_values = [head_temp["peak_c"]]
            surface_site = "head region"
            surface_note = "Head-region surface; skin unverified; not core temperature"
    site_c = sum(site_values) / len(site_values)
    surface_temp = {
        "estimate_c": round(site_c, 1),
        "estimate_f": round(site_c * 9 / 5 + 32, 1),
        "site": surface_site,
        "note": surface_note,
        "skin_verified": False,
    } if len(region) >= 20 else None

    cut_flags = {"top": cut_top, "base": cut_base,
                 "left": cut_left, "right": cut_right}
    pose = pose17.estimate(region, px, cut_flags)
    position = pose17.body_position(pose["keypoints"], cut_flags)

    return {
        "pose": pose,
        "position": position,
        "landmarks": landmarks,
        "visibility": visibility,
        "fully_visible": not (cut_top or cut_base or cut_left or cut_right),
        "posture": posture,
        "posture_reason": posture_reason,
        "aspect": round(aspect, 2),
        "height_px": height_px,
        "width_px": max_w,
        "height_m": height_m,
        "pixels": len(region),
        "head_temp": head_temp,
        "surface_temp": surface_temp,
        "surface_c": round(surface_c, 1),
        "surface_f": round(surface_c * 9 / 5 + 32, 1),
        "ambient_c": round(ambient, 1),
        "ambient_f": round(ambient * 9 / 5 + 32, 1),
        "peak_c": round(peak, 1),
        "peak_f": round(peak * 9 / 5 + 32, 1),
        "source": "thermal",
    }
