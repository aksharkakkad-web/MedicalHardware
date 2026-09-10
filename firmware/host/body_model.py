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

COLS = 32
ROWS = 24

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

    # --- surface temperature ---------------------------------------------
    # Warmest pixels within the body region only. The single hottest pixel is
    # noisy, so use the mean of the top few.
    temps = sorted((px[i] for i in region), reverse=True)
    warm = temps[: max(1, len(temps) // 10)]
    surface_c = sum(warm) / len(warm)

    return {
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
        "surface_c": round(surface_c, 1),
        "surface_f": round(surface_c * 9 / 5 + 32, 1),
        "ambient_c": round(ambient, 1),
        "ambient_f": round(ambient * 9 / 5 + 32, 1),
        "peak_c": round(peak, 1),
        "peak_f": round(peak * 9 / 5 + 32, 1),
        "source": "thermal",
    }
