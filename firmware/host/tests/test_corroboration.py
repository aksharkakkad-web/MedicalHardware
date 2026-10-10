"""A radar target with no body heat is not a person.

The radar reports a confident target, and a confident heart rate, off a desk.
Thermal is what catches it: a desk is not warm. These tests pin both halves of
that rule - the veto fires on a flat thermal scene, and it does NOT fire when
thermal simply is not there, because "no frame" is not "no body".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bridge as B  # noqa: E402
import stream.frames as F  # noqa: E402


def _state() -> B.State:
    return B.State(simulated=True)


def _flat_thermal(value: float = 22.0) -> F.ThermalFrame:
    """A uniform room: no thermal contrast, so no body."""
    return F.ThermalFrame(t_us=0, pixels=[value] * F.THERMAL_PIXELS)


def _warm_body() -> F.ThermalFrame:
    """A warm blob well clear of the 1.8 C contrast gate."""
    px = [22.0] * F.THERMAL_PIXELS
    for row in range(8, 16):
        for col in range(12, 20):
            px[row * F.THERMAL_COLS + col] = 32.0
    return F.ThermalFrame(t_us=0, pixels=px)


def _radar_target() -> F.RadarFrame:
    return F.RadarFrame(
        t_us=0, presence=True, distance_m=0.9,
        respiration_rpm=15.0, heart_rate_bpm=119.0,
    )


def test_radar_target_on_a_flat_scene_has_its_vitals_withheld():
    """The desk case: a target at range, no body heat, so no pulse is reported."""
    state = _state()
    state.apply(_flat_thermal())
    state.apply(_radar_target())
    snap = state.snapshot()

    assert snap["fusion"]["verdict"] == "radar_only"
    assert snap["radar"]["heart_rate_bpm"] is None
    assert snap["radar"]["respiration_rpm"] is None
    assert "vitals_withheld" in snap["radar"]
    # The distance is a real measurement and survives.
    assert snap["radar"]["distance_m"] == 0.9
    # Nothing downstream may pick a rate back up.
    assert snap["vitals"]["heart_rate_bpm"] is None


def test_veto_does_not_fire_when_thermal_is_absent():
    """No thermal frame means no corroboration, not a negative corroboration."""
    state = _state()
    state.apply(_radar_target())
    snap = state.snapshot()

    assert snap["radar"]["heart_rate_bpm"] == 119.0
    assert "vitals_withheld" not in snap["radar"]


def test_body_heat_present_leaves_radar_vitals_alone():
    state = _state()
    state.apply(_warm_body())
    state.apply(_radar_target())
    snap = state.snapshot()

    assert snap["fusion"]["verdict"] == "person"
    assert snap["radar"]["heart_rate_bpm"] == 119.0
    assert "vitals_withheld" not in snap["radar"]
