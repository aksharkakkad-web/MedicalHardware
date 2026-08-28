from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from inspect import signature
from math import isfinite

import pytest

from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationProgress,
    start_recalibration,
)
from backend.app.domain.feedback import MemoryEntry
from backend.app.domain.monitoring import PresenceState, derive_monitoring_snapshot
from backend.app.intelligence.baseline import (
    BaselinePolicy,
    BaselineSnapshot,
    FeatureBaseline,
    NewNormalCandidate,
    advance_new_normal,
    build_feature_baseline,
    robust_deviation,
    window_is_learning_eligible,
)
from backend.app.intelligence.fusion import AlignedFrame, FeatureEvidence
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    QualityClass,
)


_WINDOW_START = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _evidence(
    value: float | None,
    *,
    name: str = "movement",
    unit: str = "normalized",
    quality: QualityClass = QualityClass.GOOD,
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    observation_id: str = "observation_1",
    source: str = "radar",
) -> FeatureEvidence:
    return FeatureEvidence(
        source=source,
        observation_id=observation_id,
        feature=FeatureValue(
            name=name,
            value=value,
            unit=unit,
            quality_class=quality,
            quality_reasons=() if quality == QualityClass.GOOD else ("synthetic_limit",),
            purposes=(purpose,),
        ),
    )


def _frame(
    evidence: tuple[FeatureEvidence, ...],
    *,
    frame_id: str = "frame_1",
    window_start: datetime = _WINDOW_START,
) -> AlignedFrame:
    return AlignedFrame(
        frame_id=frame_id,
        tenant_id="tenant_demo",
        room_id="room_214",
        resident_id="resident_demo_a",
        window_start=window_start,
        window_end=window_start + timedelta(minutes=1),
        sources_present=tuple(sorted({item.source for item in evidence})),
        sources_missing=(),
        feature_evidence=evidence,
        agreements=(),
        contradictions=(),
    )


def _active_monitoring():
    return derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_PRESENT,
        signal_quality=0.9,
    )


def _guard(
    evidence: tuple[FeatureEvidence, ...] = (_evidence(10.0),),
    *,
    frame_id: str = "frame_1",
    window_start: datetime = _WINDOW_START,
    resident_id: str = "resident_demo_a",
    setup_version: str = "setup_v1",
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    monitoring=None,
    **flags,
):
    return window_is_learning_eligible(
        _frame(evidence, frame_id=frame_id, window_start=window_start),
        monitoring_snapshot=monitoring or _active_monitoring(),
        resident_id=resident_id,
        setup_version=setup_version,
        purpose=purpose,
        **flags,
    )


def _expected_behavior(
    *,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
) -> MemoryEntry:
    return MemoryEntry(
        entry_id="memory_expected_walk",
        description="Resident expects a higher evening movement level.",
        source_feedback_id=None,
        status="active",
        created_by="operator_007",
        created_at=_WINDOW_START,
        source_kind="operator",
        context_kind="expected_new_behavior",
        effective_from=effective_from,
        effective_until=effective_until,
    )


def _baseline_snapshot(
    *,
    resident_id: str = "resident_demo_a",
    setup_version: str = "setup_v1",
    policy_version: str = "synthetic_baseline_v1",
) -> BaselineSnapshot:
    return BaselineSnapshot(
        baseline_id="baseline_1",
        resident_id=resident_id,
        monitoring_setup_version=setup_version,
        features=(
            FeatureBaseline(
                feature_name="movement",
                purpose=FeaturePurpose.MOVEMENT,
                median=11.0,
                mad=1.0,
                iqr=2.0,
                lower_quantile=10.0,
                upper_quantile=12.0,
                resolution_floor=0.1,
                unit="normalized",
                eligible_sample_count=5,
                context_key="evening",
            ),
            FeatureBaseline(
                feature_name="respiratory_rate",
                purpose=FeaturePurpose.RESPIRATION,
                median=15.0,
                mad=1.0,
                iqr=2.0,
                lower_quantile=14.0,
                upper_quantile=16.0,
                resolution_floor=0.1,
                unit="breaths_per_min",
                eligible_sample_count=5,
                context_key="night",
            ),
        ),
        policy_version=policy_version,
    )


def _candidate(
    *,
    resident_id: str = "resident_demo_a",
    feature_name: str = "movement",
    unit: str = "normalized",
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    context_key: str = "evening",
    values: tuple[float, ...] = (),
) -> NewNormalCandidate:
    return NewNormalCandidate(
        candidate_id=f"candidate_{feature_name}",
        resident_id=resident_id,
        feature_name=feature_name,
        unit=unit,
        purpose=purpose,
        context_key=context_key,
        semantic_context_entry_id="memory_expected_walk",
        setup_version="setup_v1",
        clean_window_values=values,
        clean_window_keys=tuple(
            f"prior_frame_{index}|2026-08-28T11:{index:02d}:00+00:00"
            for index in range(len(values))
        ),
    )


def _established_calibration(setup_version: str = "setup_v1") -> CalibrationProgress:
    return CalibrationProgress(
        setup_version=setup_version,
        status=BaselineStatus.ESTABLISHED,
        eligible_windows=20,
        excluded_windows=0,
        reason="initial_setup",
    )


def test_learning_guard_binds_one_aligned_window_and_exact_evidence() -> None:
    # Break caught: eligibility can be detached from the evidence/window it approved.
    evidence = (_evidence(10.0, observation_id="observation_bound"),)
    guard = _guard(evidence, frame_id="frame_bound")

    assert guard.frame_id == "frame_bound"
    assert guard.window_start == _WINDOW_START
    assert guard.window_end == _WINDOW_START + timedelta(minutes=1)
    assert guard.resident_id == "resident_demo_a"
    assert guard.setup_version == "setup_v1"
    assert guard.purpose == FeaturePurpose.MOVEMENT
    assert guard.evidence == evidence
    assert guard.eligible is True
    assert guard.reasons == ()
    with pytest.raises(FrozenInstanceError):
        guard.eligible = False


def test_baseline_consumers_have_no_separate_raw_evidence_parameter() -> None:
    # Break caught: a caller can pair eligibility from frame A with values from frame B.
    assert "evidence" not in signature(build_feature_baseline).parameters
    assert "window_evidence" not in signature(advance_new_normal).parameters


def test_builds_robust_feature_baseline_from_bound_good_window() -> None:
    # Break caught: mean/stddev or interpolated quantiles replace the robust math.
    samples = (10.0, 10.0, 11.0, 12.0, 100.0)
    guard = _guard(
        tuple(
            _evidence(value, observation_id=f"observation_{index}")
            for index, value in enumerate(samples, start=1)
        )
    )

    baseline = build_feature_baseline(
        (guard,),
        resident_id="resident_demo_a",
        setup_version="setup_v1",
        feature_name="movement",
        purpose=FeaturePurpose.MOVEMENT,
        context_key="evening",
        resolution_floor=0.1,
        policy=BaselinePolicy(),
    )

    assert baseline.median == 11.0
    assert baseline.mad == 1.0
    assert baseline.iqr == 2.0
    assert baseline.lower_quantile == 10.0
    assert baseline.upper_quantile == 100.0
    assert baseline.eligible_sample_count == 5
    assert baseline.unit == "normalized"
    assert baseline.purpose == FeaturePurpose.MOVEMENT
    assert isfinite(robust_deviation(100.0, baseline))
    assert robust_deviation(13.9652, baseline) == pytest.approx(2.0)
    assert BaselinePolicy().test_only is True


def test_robust_deviation_uses_resolution_floor_when_spread_is_zero() -> None:
    # Break caught: zero-spread baselines divide by zero or report infinity.
    guard = _guard(
        tuple(
            _evidence(10.0, observation_id=f"observation_{index}")
            for index in range(5)
        )
    )
    baseline = build_feature_baseline(
        (guard,),
        resident_id="resident_demo_a",
        setup_version="setup_v1",
        feature_name="movement",
        purpose=FeaturePurpose.MOVEMENT,
        context_key="evening",
        resolution_floor=0.25,
        policy=BaselinePolicy(),
    )

    assert robust_deviation(10.5, baseline) == 2.0


@pytest.mark.parametrize(
    ("monitoring", "flags", "expected_reason"),
    (
        (
            derive_monitoring_snapshot(
                assignment_valid=True,
                device_healthy=True,
                presence=PresenceState.RESIDENT_AWAY,
                signal_quality=0.9,
            ),
            {},
            "resident_away",
        ),
        (
            derive_monitoring_snapshot(
                assignment_valid=True,
                device_healthy=True,
                presence=PresenceState.POSSIBLE_MULTI_PERSON,
                signal_quality=0.9,
            ),
            {},
            "possible_multi_person",
        ),
        (_active_monitoring(), {"active_candidate": True}, "active_candidate"),
        (_active_monitoring(), {"unresolved_anomaly": True}, "unresolved_anomaly"),
        (_active_monitoring(), {"setup_change": True}, "setup_change"),
        (_active_monitoring(), {"recovery_freeze": True}, "recovery_freeze"),
    ),
)
def test_learning_guard_returns_explicit_reason_for_each_window_blocker(
    monitoring, flags, expected_reason
) -> None:
    # Break caught: a monitoring/anomaly/setup/recovery gate is omitted.
    guard = _guard(monitoring=monitoring, **flags)

    assert guard.eligible is False
    assert expected_reason in guard.reasons


@pytest.mark.parametrize(
    ("quality", "value", "expected_reason"),
    (
        (QualityClass.LIMITED, 10.0, "limited_quality"),
        (QualityClass.UNUSABLE, None, "unusable_quality"),
    ),
)
def test_learning_guard_blocks_limited_and_unusable_evidence(
    quality, value, expected_reason
) -> None:
    # Break caught: non-good evidence becomes eligible numerical training data.
    guard = _guard((_evidence(value, quality=quality),))

    assert guard.eligible is False
    assert expected_reason in guard.reasons


@pytest.mark.parametrize(
    ("monitoring", "flags"),
    (
        (
            derive_monitoring_snapshot(
                assignment_valid=True,
                device_healthy=True,
                presence=PresenceState.RESIDENT_AWAY,
                signal_quality=0.9,
            ),
            {},
        ),
        (_active_monitoring(), {"active_candidate": True}),
        (_active_monitoring(), {"recovery_freeze": True}),
    ),
)
def test_blocked_guard_cannot_contribute_to_initial_baseline(monitoring, flags) -> None:
    # Break caught: initial construction bypasses its bound away/anomaly/freeze decision.
    blocked_guard = _guard(monitoring=monitoring, **flags)
    with pytest.raises(ValueError, match="eligible learning windows"):
        build_feature_baseline(
            (blocked_guard,),
            resident_id="resident_demo_a",
            setup_version="setup_v1",
            feature_name="movement",
            purpose=FeaturePurpose.MOVEMENT,
            context_key="evening",
            resolution_floor=0.1,
            policy=BaselinePolicy(minimum_samples=1),
        )


def test_guard_for_resident_a_cannot_build_resident_b_baseline() -> None:
    # Break caught: valid resident-A evidence is attributed to another resident.
    with pytest.raises(ValueError, match="resident"):
        build_feature_baseline(
            (_guard(resident_id="resident_a"),),
            resident_id="resident_b",
            setup_version="setup_v1",
            feature_name="movement",
            purpose=FeaturePurpose.MOVEMENT,
            context_key="evening",
            resolution_floor=0.1,
            policy=BaselinePolicy(minimum_samples=1),
        )


def test_guard_for_resident_a_cannot_advance_resident_b_candidate() -> None:
    # Break caught: an eligible window is rebound to a different resident during adoption.
    with pytest.raises(ValueError, match="resident"):
        advance_new_normal(
            _candidate(resident_id="resident_b"),
            baseline=_baseline_snapshot(resident_id="resident_b"),
            expected_behavior=_expected_behavior(),
            learning_guard=_guard(resident_id="resident_a"),
            calibration_progress=_established_calibration(),
            new_baseline_id="baseline_2",
            policy=BaselinePolicy(),
        )


def test_expected_behavior_adopts_only_after_five_distinct_clean_frames() -> None:
    # Break caught: semantic context immediately overwrites numerical normal.
    policy = BaselinePolicy()
    memory = _expected_behavior()
    original = _baseline_snapshot()
    candidate = _candidate()
    calibration = _established_calibration()

    assert memory.status == "active"
    assert memory.context_kind == "expected_new_behavior"
    assert candidate.semantic_context_entry_id == memory.entry_id

    for number, value in enumerate((20.0, 21.0, 22.0, 23.0), start=1):
        candidate, published = advance_new_normal(
            candidate,
            baseline=original,
            expected_behavior=memory,
            learning_guard=_guard(
                (_evidence(value, observation_id=f"observation_{number}"),),
                frame_id=f"clean_frame_{number}",
                window_start=_WINDOW_START + timedelta(minutes=number),
            ),
            calibration_progress=calibration,
            new_baseline_id="baseline_2",
            policy=policy,
        )
        assert candidate.clean_windows == number
        assert published is None
        assert original.feature("movement", "evening").median == 11.0

    candidate, published = advance_new_normal(
        candidate,
        baseline=original,
        expected_behavior=memory,
        learning_guard=_guard(
            (_evidence(24.0, observation_id="observation_5"),),
            frame_id="clean_frame_5",
            window_start=_WINDOW_START + timedelta(minutes=5),
        ),
        calibration_progress=calibration,
        new_baseline_id="baseline_2",
        policy=policy,
    )

    assert candidate.clean_windows == 5
    assert candidate.adopted_baseline_id == "baseline_2"
    assert published is not None
    assert published is not original
    assert published.prior_baseline_id == "baseline_1"
    assert published.adoption_candidate_id == candidate.candidate_id
    assert published.adoption_context_entry_id == memory.entry_id
    assert published.feature("movement", "evening").median == 22.0
    assert original.feature("movement", "evening").median == 11.0


def test_ineligible_bound_window_does_not_advance_new_normal_candidate() -> None:
    # Break caught: a recovery-frozen window contributes its bound evidence anyway.
    candidate = _candidate(values=(20.0, 21.0))
    updated, published = advance_new_normal(
        candidate,
        baseline=_baseline_snapshot(),
        expected_behavior=_expected_behavior(),
        learning_guard=_guard(
            (_evidence(22.0),),
            frame_id="blocked_frame",
            recovery_freeze=True,
        ),
        calibration_progress=_established_calibration(),
        new_baseline_id="baseline_2",
        policy=BaselinePolicy(),
    )

    assert updated.clean_window_values == (20.0, 21.0)
    assert updated.last_ineligibility_reasons == ("recovery_freeze",)
    assert published is None


@pytest.mark.parametrize(
    ("expected_behavior", "window_start", "reason"),
    (
        (
            _expected_behavior(effective_from=_WINDOW_START + timedelta(minutes=2)),
            _WINDOW_START,
            "expected_behavior_not_yet_effective",
        ),
        (
            _expected_behavior(effective_until=_WINDOW_START + timedelta(minutes=1)),
            _WINDOW_START + timedelta(minutes=1),
            "expected_behavior_expired",
        ),
    ),
)
def test_learning_window_must_be_inside_expected_behavior_effective_period(
    expected_behavior: MemoryEntry,
    window_start: datetime,
    reason: str,
) -> None:
    # Break caught: an inactive semantic window advances numerical normality.
    updated, published = advance_new_normal(
        _candidate(),
        baseline=_baseline_snapshot(),
        expected_behavior=expected_behavior,
        learning_guard=_guard(
            (_evidence(20.0),),
            frame_id=f"outside_{reason}",
            window_start=window_start,
        ),
        calibration_progress=_established_calibration(),
        new_baseline_id="baseline_2",
        policy=BaselinePolicy(),
    )

    assert updated.clean_windows == 0
    assert updated.last_ineligibility_reasons == (reason,)
    assert published is None


def test_expiry_after_partial_progress_terminates_adoption_without_publication() -> None:
    # Break caught: four clean windows publish after their expected context expires.
    expected = _expected_behavior(
        effective_from=_WINDOW_START,
        effective_until=_WINDOW_START + timedelta(minutes=5),
    )
    candidate = _candidate()
    arguments = {
        "baseline": _baseline_snapshot(),
        "expected_behavior": expected,
        "calibration_progress": _established_calibration(),
        "new_baseline_id": "baseline_2",
        "policy": BaselinePolicy(),
    }
    for number in range(1, 5):
        candidate, published = advance_new_normal(
            candidate,
            learning_guard=_guard(
                (_evidence(20.0 + number),),
                frame_id=f"effective_{number}",
                window_start=_WINDOW_START + timedelta(minutes=number),
            ),
            **arguments,
        )
        assert published is None

    expired, published = advance_new_normal(
        candidate,
        learning_guard=_guard(
            (_evidence(25.0),),
            frame_id="expired_fifth",
            window_start=_WINDOW_START + timedelta(minutes=5),
        ),
        **arguments,
    )

    assert expired.clean_windows == 4
    assert expired.last_ineligibility_reasons == ("expected_behavior_expired",)
    assert published is None

    terminated, replay_publication = advance_new_normal(
        expired,
        learning_guard=_guard(
            (_evidence(25.0),),
            frame_id="backfilled_fifth",
            window_start=_WINDOW_START + timedelta(minutes=4),
        ),
        **arguments,
    )
    assert terminated == expired
    assert replay_publication is None


def test_different_source_subsets_from_one_frame_count_once() -> None:
    # Break caught: changing sensor subsets makes one aligned frame count repeatedly.
    candidate = _candidate()
    first = _guard(
        (_evidence(20.0, observation_id="radar_1", source="radar"),),
        frame_id="shared_frame",
    )
    changed_subset = _guard(
        (_evidence(21.0, observation_id="thermal_1", source="thermal"),),
        frame_id="shared_frame",
    )
    arguments = {
        "baseline": _baseline_snapshot(),
        "expected_behavior": _expected_behavior(),
        "calibration_progress": _established_calibration(),
        "new_baseline_id": "baseline_2",
        "policy": BaselinePolicy(),
    }

    candidate, first_publish = advance_new_normal(
        candidate,
        learning_guard=first,
        **arguments,
    )
    replayed, second_publish = advance_new_normal(
        candidate,
        learning_guard=changed_subset,
        **arguments,
    )

    assert candidate.clean_windows == 1
    assert first_publish is None
    assert replayed.clean_windows == 1
    assert replayed.last_ineligibility_reasons == ("duplicate_window",)
    assert second_publish is None


def test_publication_rejects_reusing_current_baseline_id() -> None:
    # Break caught: an immutable baseline snapshot becomes its own predecessor.
    with pytest.raises(ValueError, match="new_baseline_id"):
        advance_new_normal(
            _candidate(values=(20.0, 21.0, 22.0, 23.0)),
            baseline=_baseline_snapshot(),
            expected_behavior=_expected_behavior(),
            learning_guard=_guard((_evidence(24.0),), frame_id="clean_frame_5"),
            calibration_progress=_established_calibration(),
            new_baseline_id="baseline_1",
            policy=BaselinePolicy(),
        )


def test_partial_adoption_rejects_policy_mismatch_with_retained_features() -> None:
    # Break caught: one snapshot claims a new policy for untouched old-policy facts.
    with pytest.raises(ValueError, match="policy_version"):
        advance_new_normal(
            _candidate(values=(20.0, 21.0, 22.0, 23.0)),
            baseline=_baseline_snapshot(),
            expected_behavior=_expected_behavior(),
            learning_guard=_guard((_evidence(24.0),), frame_id="clean_frame_5"),
            calibration_progress=_established_calibration(),
            new_baseline_id="baseline_2",
            policy=BaselinePolicy(policy_version="synthetic_baseline_v2"),
        )


def test_setup_change_starts_new_lineage_only_for_affected_feature_names() -> None:
    # Break caught: setup change contaminates an affected feature or resets all features.
    progress = CalibrationProgress.new(
        "setup_v1",
        dimensions=("movement", "respiratory_rate"),
    )
    changed = start_recalibration(
        progress,
        new_setup_version="setup_v2",
        reason="device_moved",
        actor_id="operator_007",
        changed_at=_WINDOW_START,
        affected_dimensions=("movement",),
    )

    affected, affected_snapshot = advance_new_normal(
        _candidate(values=(20.0, 21.0, 22.0, 23.0)),
        baseline=_baseline_snapshot(),
        expected_behavior=_expected_behavior(),
        learning_guard=_guard(
            (_evidence(24.0),),
            frame_id="movement_setup_v2_frame",
            setup_version="setup_v2",
        ),
        calibration_progress=changed,
        new_baseline_id="baseline_2",
        policy=BaselinePolicy(),
    )
    unaffected, unaffected_snapshot = advance_new_normal(
        _candidate(
            feature_name="respiratory_rate",
            unit="breaths_per_min",
            purpose=FeaturePurpose.RESPIRATION,
            context_key="night",
            values=(15.0, 16.0, 17.0, 18.0),
        ),
        baseline=_baseline_snapshot(),
        expected_behavior=_expected_behavior(),
        learning_guard=_guard(
            (
                _evidence(
                    19.0,
                    name="respiratory_rate",
                    unit="breaths_per_min",
                    purpose=FeaturePurpose.RESPIRATION,
                ),
            ),
            frame_id="respiration_setup_v2_frame",
            setup_version="setup_v2",
            purpose=FeaturePurpose.RESPIRATION,
        ),
        calibration_progress=changed,
        new_baseline_id="baseline_2",
        policy=BaselinePolicy(),
    )

    assert affected.setup_version == "setup_v2"
    assert affected.clean_window_values == (24.0,)
    assert affected_snapshot is None
    assert unaffected.setup_version == "setup_v2"
    assert unaffected.clean_window_values == (15.0, 16.0, 17.0, 18.0, 19.0)
    assert unaffected_snapshot is not None
    assert unaffected_snapshot.feature("movement", "evening") == _baseline_snapshot().feature(
        "movement", "evening"
    )


def test_affected_candidate_publishes_after_five_post_setup_windows() -> None:
    # Break caught: the pending new-setup candidate is rejected after its first window.
    original = _baseline_snapshot()
    unchanged_respiration = original.feature("respiratory_rate", "night")
    changed = start_recalibration(
        CalibrationProgress.new(
            "setup_v1",
            dimensions=("movement", "respiratory_rate"),
        ),
        new_setup_version="setup_v2",
        reason="device_moved",
        actor_id="operator_007",
        changed_at=_WINDOW_START,
        affected_dimensions=("movement",),
    )
    candidate = _candidate(values=(20.0, 21.0, 22.0, 23.0))

    for number, value in enumerate((30.0, 31.0, 32.0, 33.0), start=1):
        candidate, published = advance_new_normal(
            candidate,
            baseline=original,
            expected_behavior=_expected_behavior(),
            learning_guard=_guard(
                (_evidence(value, observation_id=f"setup_v2_observation_{number}"),),
                frame_id=f"setup_v2_frame_{number}",
                window_start=_WINDOW_START + timedelta(minutes=number),
                setup_version="setup_v2",
            ),
            calibration_progress=changed,
            new_baseline_id="baseline_2",
            policy=BaselinePolicy(),
        )
        assert candidate.setup_version == "setup_v2"
        assert candidate.clean_windows == number
        assert published is None

    candidate, published = advance_new_normal(
        candidate,
        baseline=original,
        expected_behavior=_expected_behavior(),
        learning_guard=_guard(
            (_evidence(34.0, observation_id="setup_v2_observation_5"),),
            frame_id="setup_v2_frame_5",
            window_start=_WINDOW_START + timedelta(minutes=5),
            setup_version="setup_v2",
        ),
        calibration_progress=changed,
        new_baseline_id="baseline_2",
        policy=BaselinePolicy(),
    )

    assert candidate.clean_windows == 5
    assert published is not None
    assert published.monitoring_setup_version == "setup_v2"
    assert published.prior_baseline_id == "baseline_1"
    assert published.feature("movement", "evening").median == 32.0
    assert published.feature("respiratory_rate", "night") == unchanged_respiration
    assert original.monitoring_setup_version == "setup_v1"
