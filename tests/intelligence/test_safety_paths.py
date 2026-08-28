from datetime import datetime, timedelta, timezone

import pytest

from backend.app.intelligence.degradation import (
    DegradationKind,
    assess_monitoring_degradation,
)
from backend.app.intelligence.fall_detection import (
    FallLikeState,
    SyntheticFallPolicy,
    advance_fall_like,
)
from backend.app.intelligence.fusion import AlignedFrame, align_observations
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    NormalizedObservation,
    QualityClass,
)


START = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def feature(
    name: str,
    value: float | bool | str | None,
    unit: str,
    purpose: FeaturePurpose,
    *,
    quality: QualityClass = QualityClass.GOOD,
    reasons: tuple[str, ...] = (),
) -> FeatureValue:
    return FeatureValue(name, value, unit, quality, reasons, (purpose,))


def frame(
    offset_seconds: int,
    observations: tuple[tuple[str, tuple[FeatureValue, ...]], ...],
    *,
    expected_sources: tuple[str, ...] = ("radar", "thermal"),
) -> AlignedFrame:
    window_start = START + timedelta(seconds=offset_seconds)
    window_end = window_start + timedelta(seconds=1)
    normalized = tuple(
        NormalizedObservation(
            observation_id=f"obs_{source}_{offset_seconds}",
            tenant_id="tenant_demo",
            room_id="room_214",
            resident_id="resident_demo",
            device_id=f"device_{source}",
            source=source,
            window_start=window_start,
            window_end=window_end,
            features=features,
            source_quality_class=QualityClass.GOOD,
            source_quality_reasons=(),
            processor_version=f"{source}_sim_v1",
        )
        for source, features in observations
    )
    return align_observations(
        normalized,
        frame_id=f"frame_{offset_seconds}",
        window_start=window_start,
        window_end=window_end,
        expected_sources=expected_sources,
    )


def radar_features(
    height: float,
    *,
    velocity: float = 0.0,
    position: str = "upright_like",
    movement: float = 0.3,
) -> tuple[FeatureValue, ...]:
    return (
        feature("tracked_height", height, "m", FeaturePurpose.POSTURE),
        feature("vertical_velocity", velocity, "m/s", FeaturePurpose.MOVEMENT),
        feature("position_state", position, "categorical", FeaturePurpose.POSTURE),
        feature("movement_energy", movement, "normalized", FeaturePurpose.MOVEMENT),
    )


def thermal_features(position: str) -> tuple[FeatureValue, ...]:
    return (
        feature("position_state", position, "categorical", FeaturePurpose.POSTURE),
    )


def run_fall_sequence(
    sequence: tuple[AlignedFrame, ...],
    *,
    possible_multiple_people: bool = False,
):
    assessment = None
    for current in sequence:
        assessment = advance_fall_like(
            assessment,
            current,
            possible_multiple_people=possible_multiple_people,
        )
    assert assessment is not None
    return assessment


def fall_sequence(*, include_thermal: bool = True) -> tuple[AlignedFrame, ...]:
    positions = ("upright_like", "floor_like", "floor_like", "floor_like", "floor_like")
    heights = (1.7, 0.8, 0.78, 0.78, 0.78)
    velocities = (0.0, -1.1, -0.1, 0.0, 0.0)
    movements = (0.4, 0.5, 0.1, 0.08, 0.07)
    result = []
    for index in range(5):
        sources: tuple[tuple[str, tuple[FeatureValue, ...]], ...] = (
            ("radar", radar_features(
                heights[index],
                velocity=velocities[index],
                position=positions[index],
                movement=movements[index],
            )),
        )
        if include_thermal:
            sources += (("thermal", thermal_features(positions[index])),)
        result.append(frame(index, sources))
    return tuple(result)


def test_strong_radar_with_thermal_corroboration_triggers_urgent_fast_path() -> None:
    # Break caught: valid short-lane evidence waits for anomaly persistence or an LLM.
    assessment = run_fall_sequence(fall_sequence())

    assert assessment.state == FallLikeState.CONFIRMED_FALL_LIKE
    assert assessment.urgent_triggered
    assert assessment.confidence == "high"
    assert assessment.evidence_sources == ("radar", "thermal")
    assert assessment.contradictions == ()
    assert assessment.transition_started_at == START + timedelta(seconds=2)
    assert assessment.assessed_at == START + timedelta(seconds=5)
    assert assessment.policy_version == "synthetic_fall_like_v1"
    assert assessment.test_only
    assert not assessment.clinical_authority


def test_strong_radar_without_thermal_triggers_with_lower_confidence() -> None:
    # Break caught: missing thermal either blocks valid radar evidence or is silently imputed.
    assessment = run_fall_sequence(fall_sequence(include_thermal=False))

    assert assessment.state == FallLikeState.CONFIRMED_FALL_LIKE
    assert assessment.urgent_triggered
    assert assessment.confidence == "lower"
    assert assessment.evidence_sources == ("radar",)
    assert assessment.missing_sources == ("thermal",)
    assert "thermal_corroboration_unavailable" in assessment.limitations


@pytest.mark.parametrize(
    ("name", "sequence"),
    (
        (
            "quick_sitting",
            (
                frame(0, (("radar", radar_features(1.7)),)),
                frame(1, (("radar", radar_features(
                    0.85,
                    velocity=-1.1,
                    position="seated_like",
                    movement=0.1,
                )),)),
                frame(2, (("radar", radar_features(
                    0.85,
                    position="seated_like",
                    movement=0.08,
                )),)),
            ),
        ),
        (
            "kneeling",
            (
                frame(0, (("radar", radar_features(1.7)),)),
                frame(1, (("radar", radar_features(
                    0.85,
                    velocity=-1.0,
                    position="kneeling_like",
                    movement=0.08,
                )),)),
                frame(2, (("radar", radar_features(
                    0.85,
                    position="kneeling_like",
                    movement=0.06,
                )),)),
            ),
        ),
        (
            "controlled_descent",
            (
                frame(0, (("radar", radar_features(1.7)),)),
                frame(1, (("radar", radar_features(
                    0.8,
                    velocity=-0.8,
                    position="floor_like",
                    movement=0.1,
                )),)),
                frame(2, (("radar", radar_features(
                    0.8,
                    position="floor_like",
                    movement=0.08,
                )),)),
            ),
        ),
        (
            "picking_something_up",
            (
                frame(0, (("radar", radar_features(1.7)),)),
                frame(1, (("radar", radar_features(
                    1.35,
                    velocity=-1.1,
                    position="low_like",
                    movement=0.1,
                )),)),
                frame(2, (("radar", radar_features(1.65)),)),
            ),
        ),
        (
            "intentional_lying",
            (
                frame(0, (("radar", radar_features(1.7)),)),
                frame(1, (("radar", radar_features(
                    0.8,
                    velocity=-0.5,
                    position="lying_like",
                    movement=0.1,
                )),)),
                frame(2, (("radar", radar_features(
                    0.8,
                    position="lying_like",
                    movement=0.05,
                )),)),
            ),
        ),
    ),
)
def test_common_confounders_do_not_trigger_urgent_path(
    name: str,
    sequence: tuple[AlignedFrame, ...],
) -> None:
    # Break caught: posture or one motion feature alone is treated as a fall-like match.
    assessment = run_fall_sequence(sequence)

    assert not assessment.urgent_triggered, name
    assert assessment.state in (FallLikeState.STABLE, FallLikeState.RECOVERED)


def test_contradictory_low_position_evidence_is_preserved_and_blocks_trigger() -> None:
    # Break caught: radar/thermal posture contradiction is averaged into low position.
    sequence = list(fall_sequence())
    for index in range(1, len(sequence)):
        sequence[index] = frame(
            index,
            (
                ("radar", radar_features(
                    0.8,
                    velocity=-1.1 if index == 1 else 0.0,
                    position="floor_like",
                    movement=0.08,
                )),
                ("thermal", thermal_features("upright_like")),
            ),
        )

    assessment = run_fall_sequence(tuple(sequence))

    assert not assessment.urgent_triggered
    assert assessment.contradictions == (
        "position_state:radar=floor_like,thermal=upright_like",
    )
    assert "contradictory_low_position_evidence" in assessment.limitations


def test_confirmation_after_policy_window_recovers_without_urgent_trigger() -> None:
    # Break caught: stale post-transition evidence can confirm indefinitely late.
    sequence = list(fall_sequence()[:4])
    sequence.append(frame(
        8,
        (("radar", radar_features(
            0.78,
            position="floor_like",
            movement=0.07,
        )),),
    ))

    assessment = run_fall_sequence(tuple(sequence))

    assert assessment.state == FallLikeState.RECOVERED
    assert not assessment.urgent_triggered
    assert "confirmation_window_expired" in assessment.limitations


def test_possible_multiple_people_preserves_room_evidence_without_resident_claim() -> None:
    # Break caught: ambiguous room evidence is either discarded or assigned to the resident.
    assessment = run_fall_sequence(
        fall_sequence(),
        possible_multiple_people=True,
    )

    assert assessment.urgent_triggered
    assert assessment.room_level_only
    assert "resident_attribution_uncertain" in assessment.limitations


def test_multiple_person_ambiguity_during_descent_stays_sticky_through_confirmation() -> None:
    # Break caught: clearing room ambiguity later assigns the in-progress episode to a resident.
    assessment = None
    for index, current in enumerate(fall_sequence()):
        assessment = advance_fall_like(
            assessment,
            current,
            possible_multiple_people=index == 1,
        )

    assert assessment is not None
    assert assessment.state == FallLikeState.CONFIRMED_FALL_LIKE
    assert assessment.urgent_triggered
    assert assessment.room_level_only
    assert "resident_attribution_uncertain" in assessment.limitations


def test_confirmed_assessment_recovers_on_upright_posture_and_high_movement() -> None:
    # Break caught: the current fast assessment acts as a permanent urgent event latch.
    confirmed = run_fall_sequence(fall_sequence())

    recovered = advance_fall_like(
        confirmed,
        frame(
            5,
            (
                ("radar", radar_features(
                    1.6,
                    position="upright_like",
                    movement=0.5,
                )),
                ("thermal", thermal_features("upright_like")),
            ),
        ),
    )

    assert recovered.state == FallLikeState.RECOVERED
    assert not recovered.urgent_triggered
    assert recovered.confidence == "none"
    assert "thermal_corroboration_unavailable" not in recovered.limitations


def test_confirmed_assessment_keeps_explicit_thermal_contradiction_honest() -> None:
    # Break caught: contradictory thermal evidence is mislabeled as unavailable.
    confirmed = run_fall_sequence(fall_sequence())

    still_confirmed = advance_fall_like(
        confirmed,
        frame(
            5,
            (
                ("radar", radar_features(
                    0.78,
                    position="floor_like",
                    movement=0.07,
                )),
                ("thermal", thermal_features("upright_like")),
            ),
        ),
    )

    assert still_confirmed.state == FallLikeState.CONFIRMED_FALL_LIKE
    assert still_confirmed.urgent_triggered
    assert still_confirmed.confidence == "lower"
    assert still_confirmed.contradictions == (
        "position_state:radar=floor_like,thermal=upright_like",
    )
    assert "contradictory_low_position_evidence" in still_confirmed.limitations
    assert "thermal_corroboration_unavailable" not in still_confirmed.limitations


def test_synthetic_policy_requires_version_change_for_custom_fixture_values() -> None:
    # Break caught: default policy version silently refers to different fixture thresholds.
    with pytest.raises(ValueError, match="custom policy values require"):
        SyntheticFallPolicy(max_confirmation_seconds=6.0)

    custom = SyntheticFallPolicy(
        max_confirmation_seconds=6.0,
        policy_version="synthetic_fall_like_experiment_v2",
    )
    assert custom.test_only
    assert not custom.clinical_authority


def test_fall_state_rejects_replayed_or_out_of_order_frames() -> None:
    # Break caught: replaying one frame can advance the fast-path state more than once.
    first_frame = fall_sequence()[0]
    assessment = advance_fall_like(None, first_frame)

    with pytest.raises(ValueError, match="frame must follow previous assessment"):
        advance_fall_like(assessment, first_frame)


def test_stale_and_frozen_evidence_is_operational_degradation_not_anomaly() -> None:
    # Break caught: invalid sensor data becomes resident behavior or one generic score.
    stale = feature(
        "movement_energy",
        None,
        "normalized",
        FeaturePurpose.MOVEMENT,
        quality=QualityClass.UNUSABLE,
        reasons=("stale",),
    )
    frozen = feature(
        "position_state",
        None,
        "categorical",
        FeaturePurpose.POSTURE,
        quality=QualityClass.UNUSABLE,
        reasons=("frozen",),
    )

    assessment = assess_monitoring_degradation(frame(
        0,
        (("radar", (stale,)), ("thermal", (frozen,))),
    ))

    assert assessment.degraded
    assert assessment.kinds == (
        DegradationKind.FROZEN_SIGNAL,
        DegradationKind.STALE_SIGNAL,
    )
    assert assessment.assessment_scope == "operational"
    assert not assessment.resident_anomaly
    assert assessment.evidence_sources == ("radar", "thermal")


def test_device_movement_and_environment_shift_remain_separate_evidence() -> None:
    # Break caught: setup and RF environment changes are collapsed or blamed on a resident.
    device_moved = feature(
        "device_moved",
        True,
        "boolean",
        FeaturePurpose.PRESENCE,
    )
    environment_shift = feature(
        "environment_shift",
        True,
        "boolean",
        FeaturePurpose.PRESENCE,
    )

    assessment = assess_monitoring_degradation(frame(
        0,
        (
            ("radar", (device_moved,)),
            ("wifi_csi", (environment_shift,)),
        ),
        expected_sources=("radar", "thermal", "wifi_csi"),
    ))

    assert assessment.kinds == (
        DegradationKind.DEVICE_MOVEMENT,
        DegradationKind.ENVIRONMENT_SHIFT,
    )
    assert assessment.evidence == (
        "radar:obs_radar_0:device_moved=True boolean",
        "wifi_csi:obs_wifi_csi_0:environment_shift=True boolean",
    )
    assert assessment.missing_sources == ("thermal",)
    assert not assessment.resident_anomaly
