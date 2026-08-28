from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from math import isfinite

import pytest

from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationProgress,
    start_recalibration,
)
from backend.app.domain.feedback import MemoryEntry
from backend.app.domain.monitoring import (
    PresenceState,
    derive_monitoring_snapshot,
)
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
from backend.app.intelligence.fusion import FeatureEvidence
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    QualityClass,
)


def _evidence(
    value: float | None,
    *,
    name: str = "movement",
    unit: str = "normalized",
    quality: QualityClass = QualityClass.GOOD,
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    observation_id: str = "observation_1",
) -> FeatureEvidence:
    return FeatureEvidence(
        source="radar",
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


def _active_monitoring():
    return derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_PRESENT,
        signal_quality=0.9,
    )


def _expected_behavior() -> MemoryEntry:
    return MemoryEntry(
        entry_id="memory_expected_walk",
        description="Resident expects a higher evening movement level.",
        source_feedback_id=None,
        status="active",
        created_by="operator_007",
        created_at=datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc),
        source_kind="operator",
        context_kind="expected_new_behavior",
    )


def _baseline_snapshot() -> BaselineSnapshot:
    return BaselineSnapshot(
        baseline_id="baseline_1",
        resident_id="resident_demo_a",
        monitoring_setup_version="setup_v1",
        features=(
            FeatureBaseline(
                feature_name="movement",
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
        policy_version="synthetic_baseline_v1",
    )


def _candidate(
    *,
    feature_name: str = "movement",
    unit: str = "normalized",
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    context_key: str = "evening",
    values: tuple[float, ...] = (),
) -> NewNormalCandidate:
    return NewNormalCandidate(
        candidate_id=f"candidate_{feature_name}",
        resident_id="resident_demo_a",
        feature_name=feature_name,
        unit=unit,
        purpose=purpose,
        context_key=context_key,
        semantic_context_entry_id="memory_expected_walk",
        setup_version="setup_v1",
        clean_window_values=values,
        clean_window_keys=tuple(
            f"prior_window_{index}" for index in range(len(values))
        ),
    )


def test_builds_robust_feature_baseline_from_literal_good_evidence() -> None:
    # Break caught: mean/stddev or interpolated quantiles replace the specified robust math.
    samples = (10.0, 10.0, 11.0, 12.0, 100.0)
    evidence = tuple(
        _evidence(value, observation_id=f"observation_{index}")
        for index, value in enumerate(samples, start=1)
    )

    baseline = build_feature_baseline(
        evidence,
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
    assert isfinite(robust_deviation(100.0, baseline))
    assert robust_deviation(13.9652, baseline) == pytest.approx(2.0)
    assert BaselinePolicy().test_only is True
    assert BaselinePolicy().policy_version == "synthetic_baseline_v1"


def test_robust_deviation_uses_resolution_floor_when_spread_is_zero() -> None:
    # Break caught: zero-spread baselines divide by zero or report a fabricated infinity.
    baseline = build_feature_baseline(
        tuple(
            _evidence(10.0, observation_id=f"observation_{index}")
            for index in range(5)
        ),
        feature_name="movement",
        purpose=FeaturePurpose.MOVEMENT,
        context_key="evening",
        resolution_floor=0.25,
        policy=BaselinePolicy(),
    )

    assert robust_deviation(10.5, baseline) == 2.0


@pytest.mark.parametrize(
    ("monitoring", "evidence", "flags", "expected_reason"),
    (
        (
            derive_monitoring_snapshot(
                assignment_valid=True,
                device_healthy=True,
                presence=PresenceState.RESIDENT_AWAY,
                signal_quality=0.9,
            ),
            (_evidence(10.0),),
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
            (_evidence(10.0),),
            {},
            "possible_multi_person",
        ),
        (
            _active_monitoring(),
            (_evidence(10.0, quality=QualityClass.LIMITED),),
            {},
            "limited_quality",
        ),
        (
            _active_monitoring(),
            (_evidence(None, quality=QualityClass.UNUSABLE),),
            {},
            "unusable_quality",
        ),
        (_active_monitoring(), (_evidence(10.0),), {"active_candidate": True}, "active_candidate"),
        (
            _active_monitoring(),
            (_evidence(10.0),),
            {"unresolved_anomaly": True},
            "unresolved_anomaly",
        ),
        (_active_monitoring(), (_evidence(10.0),), {"setup_change": True}, "setup_change"),
        (
            _active_monitoring(),
            (_evidence(10.0),),
            {"recovery_freeze": True},
            "recovery_freeze",
        ),
    ),
)
def test_learning_guard_returns_explicit_reason_for_each_blocker(
    monitoring, evidence, flags, expected_reason
) -> None:
    # Break caught: any safety/quality gate is accidentally omitted or made implicit.
    decision = window_is_learning_eligible(
        evidence,
        monitoring_snapshot=monitoring,
        purpose=FeaturePurpose.MOVEMENT,
        **flags,
    )

    assert decision.eligible is False
    assert expected_reason in decision.reasons


def test_clean_window_is_learning_eligible_and_decision_is_immutable() -> None:
    # Break caught: a clean good-quality resident-present window is never learnable.
    decision = window_is_learning_eligible(
        (_evidence(10.0),),
        monitoring_snapshot=_active_monitoring(),
        purpose=FeaturePurpose.MOVEMENT,
    )

    assert decision.eligible is True
    assert decision.reasons == ()
    with pytest.raises(FrozenInstanceError):
        decision.eligible = False


def test_expected_behavior_is_semantic_immediately_but_adopts_after_five_clean_windows() -> None:
    # Break caught: trusted context immediately overwrites numerical normal, or never adopts.
    policy = BaselinePolicy()
    memory = _expected_behavior()
    original = _baseline_snapshot()
    candidate = _candidate()
    clean = window_is_learning_eligible(
        (_evidence(20.0),),
        monitoring_snapshot=_active_monitoring(),
        purpose=FeaturePurpose.MOVEMENT,
    )
    calibration = CalibrationProgress(
        setup_version="setup_v1",
        status=BaselineStatus.ESTABLISHED,
        eligible_windows=20,
        excluded_windows=0,
        reason="initial_setup",
    )

    assert memory.status == "active"
    assert memory.context_kind == "expected_new_behavior"
    assert candidate.semantic_context_entry_id == memory.entry_id

    for window_number, value in enumerate((20.0, 21.0, 22.0, 23.0), start=1):
        candidate, published = advance_new_normal(
            candidate,
            baseline=original,
            expected_behavior=memory,
            window_evidence=(
                _evidence(value, observation_id=f"clean_window_{window_number}"),
            ),
            learning_guard=clean,
            calibration_progress=calibration,
            new_baseline_id="baseline_2",
            policy=policy,
        )
        assert candidate.clean_windows == window_number
        assert published is None
        assert original.feature("movement", "evening").median == 11.0

    candidate, published = advance_new_normal(
        candidate,
        baseline=original,
        expected_behavior=memory,
        window_evidence=(_evidence(24.0, observation_id="clean_window_5"),),
        learning_guard=clean,
        calibration_progress=calibration,
        new_baseline_id="baseline_2",
        policy=policy,
    )

    assert candidate.clean_windows == 5
    assert candidate.adopted_baseline_id == "baseline_2"
    assert published is not None
    assert published is not original
    assert published.baseline_id == "baseline_2"
    assert published.prior_baseline_id == "baseline_1"
    assert published.adoption_candidate_id == candidate.candidate_id
    assert published.adoption_context_entry_id == memory.entry_id
    assert published.feature("movement", "evening").median == 22.0
    assert published.feature("movement", "evening").eligible_sample_count == 5
    assert original.feature("movement", "evening").median == 11.0


def test_ineligible_window_does_not_advance_new_normal_candidate() -> None:
    # Break caught: dirty windows count toward the five-window adoption threshold.
    candidate = _candidate(values=(20.0, 21.0))
    blocked = window_is_learning_eligible(
        (_evidence(22.0),),
        monitoring_snapshot=_active_monitoring(),
        purpose=FeaturePurpose.MOVEMENT,
        recovery_freeze=True,
    )

    updated, published = advance_new_normal(
        candidate,
        baseline=_baseline_snapshot(),
        expected_behavior=_expected_behavior(),
        window_evidence=(_evidence(22.0),),
        learning_guard=blocked,
        calibration_progress=CalibrationProgress.new("setup_v1"),
        new_baseline_id="baseline_2",
        policy=BaselinePolicy(),
    )

    assert updated.clean_window_values == (20.0, 21.0)
    assert updated.last_ineligibility_reasons == ("recovery_freeze",)
    assert published is None


def test_replayed_window_does_not_count_as_a_separate_clean_window() -> None:
    # Break caught: retrying one clean observation can satisfy the adoption threshold.
    candidate = _candidate()
    evidence = (_evidence(20.0, observation_id="same_window"),)
    clean = window_is_learning_eligible(
        evidence,
        monitoring_snapshot=_active_monitoring(),
        purpose=FeaturePurpose.MOVEMENT,
    )
    arguments = {
        "baseline": _baseline_snapshot(),
        "expected_behavior": _expected_behavior(),
        "window_evidence": evidence,
        "learning_guard": clean,
        "calibration_progress": CalibrationProgress.new("setup_v1"),
        "new_baseline_id": "baseline_2",
        "policy": BaselinePolicy(),
    }

    candidate, first_publish = advance_new_normal(candidate, **arguments)
    replayed, second_publish = advance_new_normal(candidate, **arguments)

    assert candidate.clean_windows == 1
    assert first_publish is None
    assert replayed.clean_windows == 1
    assert replayed.last_ineligibility_reasons == ("duplicate_window",)
    assert second_publish is None


def test_setup_change_starts_new_lineage_only_for_affected_feature_names() -> None:
    # Break caught: a setup change either contaminates affected progress or resets every feature.
    progress = CalibrationProgress.new(
        "setup_v1",
        dimensions=("movement", "respiratory_rate"),
    )
    changed = start_recalibration(
        progress,
        new_setup_version="setup_v2",
        reason="device_moved",
        actor_id="operator_007",
        changed_at=datetime(2026, 8, 28, 13, 0, tzinfo=timezone.utc),
        affected_dimensions=("movement",),
    )
    clean_movement = window_is_learning_eligible(
        (_evidence(24.0),),
        monitoring_snapshot=_active_monitoring(),
        purpose=FeaturePurpose.MOVEMENT,
    )
    clean_respiration = window_is_learning_eligible(
        (
            _evidence(
                19.0,
                name="respiratory_rate",
                unit="breaths_per_min",
                purpose=FeaturePurpose.RESPIRATION,
            ),
        ),
        monitoring_snapshot=_active_monitoring(),
        purpose=FeaturePurpose.RESPIRATION,
    )

    affected, affected_snapshot = advance_new_normal(
        _candidate(values=(20.0, 21.0, 22.0, 23.0)),
        baseline=_baseline_snapshot(),
        expected_behavior=_expected_behavior(),
        window_evidence=(_evidence(24.0),),
        learning_guard=clean_movement,
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
        window_evidence=(
            _evidence(
                19.0,
                name="respiratory_rate",
                unit="breaths_per_min",
                purpose=FeaturePurpose.RESPIRATION,
            ),
        ),
        learning_guard=clean_respiration,
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
