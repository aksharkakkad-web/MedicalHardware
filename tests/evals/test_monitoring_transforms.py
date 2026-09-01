from datetime import timedelta

import pytest

from evals.monitoring.scenarios import SUITE_START, _numeric_frame
from evals.monitoring.transforms import FrameTransformSpec, transform_frames


def test_transform_is_deterministic_and_preserves_identity() -> None:
    frames = (_numeric_frame("transform_case", SUITE_START, 0, 0.5),)
    spec = FrameTransformSpec(seed=7, time_shift_seconds=60, numeric_jitter=0.03)

    first = transform_frames(frames, spec)
    second = transform_frames(frames, spec)

    assert first == second
    assert first != frames
    assert first[0].tenant_id == frames[0].tenant_id
    assert first[0].resident_id == frames[0].resident_id
    assert first[0].window_start == frames[0].window_start + timedelta(seconds=60)


def test_transform_can_drop_one_source_but_not_every_source() -> None:
    frames = (_numeric_frame("transform_case", SUITE_START, 0, 0.5),)

    with pytest.raises(ValueError, match="every source"):
        transform_frames(frames, FrameTransformSpec(seed=1, drop_sources=("radar",)))


def test_transform_rejects_unbounded_numeric_jitter() -> None:
    with pytest.raises(ValueError, match="numeric_jitter"):
        FrameTransformSpec(seed=1, numeric_jitter=0.5)
