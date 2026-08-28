from datetime import datetime, timedelta, timezone

import pytest

from backend.app.intelligence import (
    FeaturePurpose,
    FeatureValue,
    NormalizedObservation,
    QualityClass,
    align_observations,
    quality_allows_detection,
    quality_allows_learning,
)


WINDOW_START = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
WINDOW_END = WINDOW_START + timedelta(seconds=5)


def feature(
    name: str,
    value: float | int | bool | str | None,
    unit: str,
    quality: QualityClass,
    purposes: tuple[FeaturePurpose, ...],
) -> FeatureValue:
    return FeatureValue(name, value, unit, quality, (), purposes)


def observation(
    source: str,
    *features: FeatureValue,
    window_start: datetime = WINDOW_START,
    window_end: datetime = WINDOW_END,
) -> NormalizedObservation:
    return NormalizedObservation(
        observation_id=f"obs_{source}",
        tenant_id="tenant_demo",
        room_id="room_214",
        resident_id="resident_demo",
        device_id="device_room_214",
        source=source,
        window_start=window_start,
        window_end=window_end,
        features=features,
        source_quality_class=QualityClass.GOOD,
        source_quality_reasons=(),
        processor_version=f"{source}_sim_v1",
    )


def radar_position(value: str) -> NormalizedObservation:
    return observation(
        "radar",
        feature(
            "position_state",
            value,
            "categorical",
            QualityClass.GOOD,
            (FeaturePurpose.POSTURE,),
        ),
    )


def thermal_position(value: str) -> NormalizedObservation:
    return observation(
        "thermal",
        feature(
            "position_state",
            value,
            "categorical",
            QualityClass.GOOD,
            (FeaturePurpose.POSTURE,),
        ),
    )


def test_unusable_feature_cannot_carry_a_numeric_value() -> None:
    with pytest.raises(ValueError, match="unusable feature value must be None"):
        FeatureValue(
            "movement_energy",
            0.4,
            "normalized",
            QualityClass.UNUSABLE,
            ("stale",),
            (FeaturePurpose.MOVEMENT,),
        )


def test_good_feature_requires_a_value_and_purpose() -> None:
    with pytest.raises(ValueError, match="usable feature value must not be None"):
        FeatureValue(
            "movement_energy",
            None,
            "normalized",
            QualityClass.GOOD,
            (),
            (FeaturePurpose.MOVEMENT,),
        )
    with pytest.raises(ValueError, match="good feature must declare at least one purpose"):
        FeatureValue(
            "movement_energy",
            0.4,
            "normalized",
            QualityClass.GOOD,
            (),
            (),
        )


def test_feature_can_support_movement_but_not_respiration() -> None:
    movement_feature = feature(
        "movement_energy",
        0.4,
        "normalized",
        QualityClass.GOOD,
        (FeaturePurpose.MOVEMENT,),
    )

    assert quality_allows_detection(movement_feature, FeaturePurpose.MOVEMENT)
    assert not quality_allows_detection(
        movement_feature, FeaturePurpose.RESPIRATION
    )


def test_only_good_feature_values_may_learn() -> None:
    good = feature(
        "movement_energy",
        0.4,
        "normalized",
        QualityClass.GOOD,
        (FeaturePurpose.MOVEMENT,),
    )
    limited = feature(
        "movement_energy",
        0.4,
        "normalized",
        QualityClass.LIMITED,
        (FeaturePurpose.MOVEMENT,),
    )
    unusable = feature(
        "movement_energy",
        None,
        "normalized",
        QualityClass.UNUSABLE,
        (FeaturePurpose.MOVEMENT,),
    )

    assert quality_allows_learning(good, FeaturePurpose.MOVEMENT)
    assert not quality_allows_learning(limited, FeaturePurpose.MOVEMENT)
    assert not quality_allows_learning(unusable, FeaturePurpose.MOVEMENT)


def test_alignment_preserves_missing_source_and_position_contradiction() -> None:
    frame = align_observations(
        (radar_position("floor_like"), thermal_position("upright_like")),
        frame_id="frame_1",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        expected_sources=("radar", "thermal", "wifi_csi"),
    )

    assert frame.sources_present == ("radar", "thermal")
    assert frame.sources_missing == ("wifi_csi",)
    assert frame.contradictions == (
        "position_state:radar=floor_like,thermal=upright_like",
    )


def test_alignment_preserves_conflicting_categorical_evidence_from_one_source() -> None:
    frame = align_observations(
        (radar_position("floor_like"), radar_position("upright_like")),
        frame_id="frame_1b",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        expected_sources=("radar",),
    )

    assert frame.contradictions == (
        "position_state:radar=floor_like,radar=upright_like",
    )


def test_alignment_records_same_value_evidence_from_independent_sources() -> None:
    frame = align_observations(
        (radar_position("upright_like"), thermal_position("upright_like")),
        frame_id="frame_2",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        expected_sources=("thermal", "radar"),
    )

    assert frame.agreements == ("position_state:radar=thermal=upright_like",)
    assert tuple((item.source, item.feature.name) for item in frame.feature_evidence) == (
        ("radar", "position_state"),
        ("thermal", "position_state"),
    )


def test_alignment_renders_each_agreeing_source_once() -> None:
    frame = align_observations(
        (
            radar_position("upright_like"),
            radar_position("upright_like"),
            thermal_position("upright_like"),
        ),
        frame_id="frame_2a",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        expected_sources=("radar", "thermal"),
    )

    assert frame.agreements == ("position_state:radar=thermal=upright_like",)


def test_alignment_groups_equal_evidence_even_when_sources_sort_between_it() -> None:
    frame = align_observations(
        (
            radar_position("upright_like"),
            thermal_position("floor_like"),
            observation(
                "wifi_csi",
                feature(
                    "position_state",
                    "upright_like",
                    "categorical",
                    QualityClass.GOOD,
                    (FeaturePurpose.POSTURE,),
                ),
            ),
        ),
        frame_id="frame_2b",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        expected_sources=("radar", "thermal", "wifi_csi"),
    )

    assert frame.agreements == ("position_state:radar=wifi_csi=upright_like",)


def test_alignment_does_not_equate_boolean_and_numeric_evidence() -> None:
    frame = align_observations(
        (
            observation(
                "radar",
                feature(
                    "presence_hint",
                    True,
                    "flag",
                    QualityClass.GOOD,
                    (FeaturePurpose.PRESENCE,),
                ),
            ),
            observation(
                "thermal",
                feature(
                    "presence_hint",
                    1,
                    "flag",
                    QualityClass.GOOD,
                    (FeaturePurpose.PRESENCE,),
                ),
            ),
        ),
        frame_id="frame_2c",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        expected_sources=("radar", "thermal"),
    )

    assert frame.agreements == ()


def test_alignment_rejects_observations_outside_the_target_window() -> None:
    out_of_window = observation(
        "radar",
        feature(
            "movement_energy",
            0.4,
            "normalized",
            QualityClass.GOOD,
            (FeaturePurpose.MOVEMENT,),
        ),
        window_end=WINDOW_END + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="observation window must fall within frame window"):
        align_observations(
            (out_of_window,),
            frame_id="frame_3",
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            expected_sources=("radar",),
        )
