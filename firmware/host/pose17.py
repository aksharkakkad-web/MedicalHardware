"""COCO-17 skeleton estimated from a 32x24 thermal silhouette.

The 17 slots are the COCO standard, so the output plugs into anything that
speaks that format. What differs from a camera-based estimator is that slots
are filled only where the sensor can actually support them, and every slot
carries a confidence and, when empty, a reason.

What this sensor can and cannot resolve:

  - A person filling the frame at ~3 m occupies roughly 22 rows by 5 columns.
    That is enough to locate a shoulder line, hips, knees and ankles along the
    body axis, and to find limbs when they are held away from the torso.
  - It is not enough for eyes, ears or a distinct nose. A whole head is two to
    three pixels across. Those four facial slots are therefore never filled,
    and `nose` is reported as the head centroid with that stated.
  - Left/right are *image* left and right. Which is the subject's left depends
    on which way they face, and this sensor cannot tell.

Anatomical band positions are standard proportions of standing height. They
locate where to *look* in the silhouette; the actual coordinate always comes
from measured warm pixels in that band, never from the proportion itself. When
a band contains no body pixels, the slot stays empty.
"""

from __future__ import annotations

import math

COLS = 32
ROWS = 24

COCO_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# Drawing order for the skeleton, by name.
COCO_EDGES = [
    ("left_shoulder", "right_shoulder"), ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"), ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"), ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"), ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
    ("nose", "left_shoulder"), ("nose", "right_shoulder"),
]

# Fraction of standing height, measured from the top of the head.
BANDS = {
    "nose": 0.06,
    "shoulder": 0.18,
    "elbow": 0.32,
    "wrist": 0.45,
    "hip": 0.53,
    "knee": 0.75,
    "ankle": 0.97,
}

_UNRESOLVABLE = "below sensor resolution (a head is 2-3 px across)"


def _rows_of(region: set[int]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for i in region:
        r, c = divmod(i, COLS)
        out.setdefault(r, []).append(c)
    for r in out:
        out[r].sort()
    return out


def estimate(region: set[int], px: list[float], cut_flags: dict) -> dict:
    """Fill COCO-17 slots from a connected warm region."""
    rows = _rows_of(region)
    if not rows:
        return {"keypoints": {}, "found": 0, "note": "no body region"}

    ys = sorted(rows)
    top, base = ys[0], ys[-1]
    height = base - top + 1

    kp: dict[str, dict] = {}

    def miss(name, reason):
        kp[name] = {"x": None, "y": None, "confidence": 0.0, "reason": reason}

    def band_row(frac: float) -> int:
        return int(round(top + frac * (height - 1)))

    def widest_near(r: int, tol: int = 1):
        """Left and right extremes near row r, searching a little either way."""
        best = None
        for rr in range(r - tol, r + tol + 1):
            if rr in rows:
                lo, hi = rows[rr][0], rows[rr][-1]
                if best is None or (hi - lo) > (best[1] - best[0]):
                    best = (lo, hi, rr)
        return best

    # --- facial slots: physically unresolvable -----------------------------
    for n in ("left_eye", "right_eye", "left_ear", "right_ear"):
        miss(n, _UNRESOLVABLE)

    # --- nose: head centroid, only if the head is in frame -----------------
    if cut_flags.get("top"):
        miss("nose", "head is outside the frame")
    else:
        head_rows = [r for r in ys if r <= band_row(0.13)]
        if head_rows:
            cols = [c for r in head_rows for c in rows[r]]
            kp["nose"] = {
                "x": round(sum(cols) / len(cols), 2),
                "y": round(sum(head_rows) / len(head_rows), 2),
                "confidence": 0.5,
                "reason": "head centroid, not an actual nose",
            }
        else:
            miss("nose", "no head region found")

    # --- paired landmarks along the body axis ------------------------------
    # Confidence drops for limb joints, which are only truly visible when the
    # limb is held away from the torso; otherwise the position falls back to
    # the silhouette edge at the anatomically expected height.
    paired = [
        ("shoulder", 0.75, False),
        ("elbow", 0.4, True),
        ("wrist", 0.35, True),
        ("hip", 0.6, False),
        ("knee", 0.45, True),
        ("ankle", 0.4, True),
    ]
    body_width = max((rows[r][-1] - rows[r][0] + 1) for r in ys)

    for part, base_conf, is_limb in paired:
        frac = BANDS[part]
        r = band_row(frac)
        if r > base or r < top:
            miss(f"left_{part}", "outside the visible silhouette")
            miss(f"right_{part}", "outside the visible silhouette")
            continue
        if (part in ("knee", "ankle") and cut_flags.get("base")) or (
            part in ("shoulder", "elbow") and cut_flags.get("top")
        ):
            miss(f"left_{part}", "body is cut off at the frame edge here")
            miss(f"right_{part}", "body is cut off at the frame edge here")
            continue

        found = widest_near(r)
        if found is None:
            miss(f"left_{part}", "no body pixels at this height")
            miss(f"right_{part}", "no body pixels at this height")
            continue

        lo, hi, rr = found
        w = hi - lo + 1
        conf = base_conf
        note = ""
        if is_limb:
            # A limb held clear of the torso widens the silhouette. Without
            # that widening the joint is inferred from proportion, so say so.
            if w >= 1.25 * body_width * 0.6:
                conf = min(0.7, base_conf + 0.25)
                note = "limb separated from torso"
            else:
                conf = base_conf * 0.6
                note = "limb against the body; position inferred from proportion"
        if cut_flags.get("left"):
            conf *= 0.6
        if cut_flags.get("right"):
            conf *= 0.6

        kp[f"left_{part}"] = {"x": float(lo), "y": float(rr),
                              "confidence": round(conf, 2), "reason": note}
        kp[f"right_{part}"] = {"x": float(hi), "y": float(rr),
                               "confidence": round(conf, 2), "reason": note}

    found = sum(1 for n in COCO_NAMES if kp.get(n, {}).get("x") is not None)
    return {
        "keypoints": kp,
        "found": found,
        "total": len(COCO_NAMES),
        "left_right": "image left/right, not the subject's",
    }


def body_position(kp: dict, cut_flags: dict) -> dict:
    """Posture from the keypoints, with the geometry that produced it."""

    def pt(n):
        k = kp.get(n)
        return (k["x"], k["y"]) if k and k["x"] is not None else None

    def midpoint(a, b):
        pa, pb = pt(a), pt(b)
        if pa and pb:
            return ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
        return pa or pb

    sh = midpoint("left_shoulder", "right_shoulder")
    hip = midpoint("left_hip", "right_hip")
    ank = midpoint("left_ankle", "right_ankle")

    if not sh or not hip:
        return {"position": "unknown",
                "reason": "need both a shoulder line and hips",
                "torso_angle_deg": None}

    # Angle of the torso from vertical, in image space.
    dx, dy = hip[0] - sh[0], hip[1] - sh[1]
    torso_deg = abs(math.degrees(math.atan2(dx, dy if dy else 1e-6)))

    if cut_flags.get("base") and not ank:
        return {"position": "seated or lower body out of frame",
                "reason": f"torso {torso_deg:.0f} deg from vertical, legs not visible",
                "torso_angle_deg": round(torso_deg, 1)}

    if torso_deg > 55:
        pos, why = "lying down", f"torso {torso_deg:.0f} deg from vertical"
    elif torso_deg > 30:
        pos, why = "leaning or bending", f"torso {torso_deg:.0f} deg from vertical"
    elif ank and hip:
        leg = abs(ank[1] - hip[1])
        trunk = abs(hip[1] - sh[1]) or 1
        # Standing legs are longer than the trunk in image space; sitting
        # foreshortens them.
        pos = "standing" if leg > 1.1 * trunk else "sitting"
        why = f"leg span {leg:.1f} px vs trunk {trunk:.1f} px"
    else:
        pos, why = "upright", f"torso {torso_deg:.0f} deg from vertical"

    return {"position": pos, "reason": why, "torso_angle_deg": round(torso_deg, 1)}
