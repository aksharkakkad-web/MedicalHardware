"""A NaN must never reach the dashboard.

One NaN thermal pixel entered the motion detector's running background and
stayed there for good. From then on every snapshot carried a bare NaN token,
the browser's JSON.parse rejected every message, and the dashboard showed the
thermal and radar feeds as down while both were streaming at full rate. These
tests pin both layers of the fix: the background cannot be poisoned, and the
bridge cannot emit anything that is not strict JSON.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bridge as B  # noqa: E402
import motion_body as M  # noqa: E402


def _frame(value: float = 30.0) -> list[float]:
    return [value] * (M.COLS * M.ROWS)


def test_one_nan_pixel_does_not_poison_the_background():
    """Pixel 0 is the case that bit: max() returns NaN only when it comes first."""
    mb = M.MotionBody()
    for _ in range(25):
        mb.update(_frame())
    bad = _frame()
    bad[0] = float("nan")
    mb.update(bad)
    for _ in range(5):
        mb.update(_frame())
    assert all(math.isfinite(b) for b in mb.bg)
    assert math.isfinite(mb.last_diag["max_delta_c"])


def test_nan_in_the_seed_frame_is_reseeded():
    mb = M.MotionBody()
    first = _frame()
    first[0] = float("nan")
    mb.update(first)
    for _ in range(25):
        mb.update(_frame())
    assert all(math.isfinite(b) for b in mb.bg)
    assert math.isfinite(mb.last_diag["max_delta_c"])


def test_snapshot_serialises_as_strict_json():
    """Non-finite floats become None, at any depth, and nothing else changes."""
    snap = {
        "a": float("nan"),
        "b": [1.5, float("inf"), {"c": -float("inf")}],
        "d": (2.0, float("nan")),
        "e": "ok",
        "f": 3,
        "g": True,
        "h": None,
    }
    safe = B.json_safe(snap)
    assert safe == {
        "a": None,
        "b": [1.5, None, {"c": None}],
        "d": [2.0, None],
        "e": "ok",
        "f": 3,
        "g": True,
        "h": None,
    }
    json.dumps(safe, allow_nan=False)  # raises if anything non-finite survived
