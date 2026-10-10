"""Find the person by what moved, not by what is warm.

The absolute-temperature approach failed on real hardware and the failure is
worth recording. The carrier self-heats, producing a 30-34 C stripe down column
0 of every frame. That stripe set the scene peak, the peak set the contrast
threshold, and the threshold landed above the temperature of an actual person
in a 29-31 C room - so the detector locked onto the board's own heat and
reported a frozen aspect ratio of 2.33 for 311 consecutive samples while
someone fell over in front of it three times.

Background subtraction fixes this at the root rather than by tuning a number.
A per-pixel running background absorbs anything static - self-heating, sunlit
walls, radiators, a laptop - and what remains is whatever moved. It also makes
the detector independent of absolute temperature, so it works on a person in a
warm room where thermal contrast is almost nil.

The trade: a person who stays still for longer than the background time constant
fades into it. That is the correct trade for detecting a fall, which is by
definition a change.
"""

from __future__ import annotations

import math

COLS = 32
ROWS = 24

# Background adaptation rate per frame. At ~8 Hz this is a time constant of
# roughly 25 s: long enough that someone standing still stays visible through a
# fall, short enough to absorb a radiator switching on.
ALPHA = 0.005

# A pixel must exceed the background by this much to count as moved. Sensor
# NETD is about 0.1 K, so 1.2 C is comfortably above noise while still catching
# a clothed torso.
FG_THRESHOLD_C = 1.2

# Hard floor. Below this the detector would chase sensor noise.
FG_FLOOR_C = 0.45

MIN_REGION_PX = 6

# Hysteresis band. Between these the shape is ambiguous and no state change is
# reported, which stops the orientation flapping for anyone near square-on.
UPRIGHT_ASPECT = 1.35
HORIZONTAL_ASPECT = 0.80


class MotionBody:
    def __init__(self) -> None:
        self.bg: list[float] | None = None
        self.frames = 0
        # Always populated, so "nothing detected" can be diagnosed without
        # guessing at which threshold was responsible.
        self.last_diag: dict = {}

    def update(self, px: list[float]) -> dict | None:
        if self.bg is None:
            self.bg = list(px)
            self.frames = 1
            return None
        # Adapt first, then measure, so a stationary scene converges quickly.
        a = ALPHA if self.frames > 40 else 0.05
        # A non-finite pixel must never reach the background. A running average
        # that takes in one NaN keeps it forever; a NaN at pixel 0 then made
        # max() return NaN on every frame, which reached the dashboard as a bare
        # NaN token the browser refused to parse, freezing every panel. A pixel
        # whose background is already non-finite is re-seeded from the reading.
        self.bg = [
            b if not math.isfinite(p) else p if not math.isfinite(b) else b + (p - b) * a
            for b, p in zip(self.bg, px)
        ]
        self.frames += 1
        if self.frames < 20:
            return None  # background not settled yet

        # A pixel with no reading shows no motion rather than an invented delta.
        fg = [p - b if math.isfinite(p) and math.isfinite(b) else 0.0
              for p, b in zip(px, self.bg)]

        # Adaptive threshold. A fixed 1.2 C found nothing on real hardware: in a
        # 29-31 C room a clothed person barely exceeds the background, and the
        # figure was chosen from datasheet NETD rather than from the scene. Use
        # the frame's own spread instead, floored so noise cannot trigger.
        pos = sorted(d for d in fg if d > 0)
        noise = pos[int(len(pos) * 0.6)] if len(pos) > 20 else 0.0
        thr = max(FG_FLOOR_C, min(FG_THRESHOLD_C, noise * 2.5))

        mask = [d >= thr for d in fg]
        self.last_diag = {
            "threshold_c": round(thr, 2),
            "max_delta_c": round(max(fg), 2) if fg else 0.0,
            "pixels_over": sum(mask),
        }
        if sum(mask) < MIN_REGION_PX:
            return None

        region = self._largest(mask)
        if len(region) < MIN_REGION_PX:
            return None

        rows: dict[int, list[int]] = {}
        for i in region:
            r, c = divmod(i, COLS)
            rows.setdefault(r, []).append(c)
        ys = sorted(rows)
        top, base = ys[0], ys[-1]
        cols = [c for r in ys for c in rows[r]]
        height = base - top + 1
        width = max(rows[r][-1] - rows[r][0] + 1 for r in ys) if rows else 1
        width = max(width, max(cols) - min(cols) + 1)

        cy = sum(r for r in ys for _ in rows[r]) / len(cols)
        cx = sum(cols) / len(cols)
        aspect = height / max(1, width)

        # Clipping makes the ratio meaningless. Standing close to the sensor
        # fills the frame side to side, so the region measures "wide" for the
        # same reason a fallen person does - the true width is simply larger
        # than the field of view. The same applies vertically. When either axis
        # is clipped on both sides, orientation is unknown rather than
        # horizontal.
        clipped_h = min(cols) <= 0 and max(cols) >= COLS - 1
        clipped_v = top <= 0 and base >= ROWS - 1
        orientation_known = not (clipped_h or clipped_v)

        # Hysteresis. A single threshold at 1.0 flaps frame to frame for anyone
        # near square-on; separate thresholds mean a state only changes when
        # the shape clearly changes.
        if not orientation_known:
            orientation = "unknown"
        elif aspect >= UPRIGHT_ASPECT:
            orientation = "upright"
        elif aspect <= HORIZONTAL_ASPECT:
            orientation = "horizontal"
        else:
            orientation = "ambiguous"

        return {
            "pixels": len(region),
            "box": [min(cols), top, max(cols), base],
            "centroid": [round(cx, 2), round(cy, 2)],
            "height_px": height,
            "width_px": width,
            "aspect": round(aspect, 2),
            "orientation": orientation,
            "orientation_known": orientation_known,
            "clipped_h": clipped_h,
            "clipped_v": clipped_v,
            "horizontal": orientation == "horizontal",
            "upright": orientation == "upright",
            "peak_delta_c": round(max(fg), 1),
            "touches_bottom": base >= ROWS - 1,
            **self.last_diag,
        }

    @staticmethod
    def _largest(mask: list[bool]) -> set[int]:
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
