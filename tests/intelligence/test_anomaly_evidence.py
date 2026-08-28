from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from inspect import signature

import pytest

from backend.app.intelligence.anomaly import (
    AnomalyState,
    SyntheticAnomalyPolicy,
    advance_episode,
)
from backend.app.intelligence.baseline import (
    BaselineSnapshot,
    FeatureBaseline,
)
from backend.app.intelligence.evidence import build_evidence_packet
from backend.app.intelligence.fusion import AlignedFrame, FeatureEvidence
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    QualityClass,
)


_START = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)


def _feature_evidence(
    value: float | None,
    *,
    name: str = "movement",
    source: str = "radar",
    observation_id: str = "observation_1",
    unit: str = "normalized",
    quality: QualityClass = QualityClass.GOOD,
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
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
    second: int,
    value: float | None,
    *,
    quality: QualityClass = QualityClass.GOOD,
    sources_missing: tuple[str, ...] = (),
    agreements: tuple[str, ...] = (),
    contradictions: tuple[str, ...] = (),
) -> AlignedFrame:
    evidence = () if value is None else (
        _feature_evidence(
            value,
            observation_id=f"observation_{second}",
            quality=quality,
        ),
    )
    window_start = _START + timedelta(seconds=second)
    return AlignedFrame(
        frame_id=f"frame_{second}",
        window_start=window_start,
        window_end=window_start + timedelta(seconds=1),
        sources_present=() if not evidence else ("radar",),
        sources_missing=sources_missing,
        feature_evidence=evidence,
        agreements=agreements,
        contradictions=contradictions,
    )


def _baseline() -> BaselineSnapshot:
    return BaselineSnapshot(
        baseline_id="baseline_7",
        resident_id="resident_demo_a",
        monitoring_setup_version="setup_room_214_v3",
        features=(
            FeatureBaseline(
                feature_name="movement",
                purpose=FeaturePurpose.MOVEMENT,
                median=10.0,
                mad=0.0,
                iqr=0.0,
                lower_quantile=10.0,
                upper_quantile=10.0,
                resolution_floor=1.0,
                unit="normalized",
                eligible_sample_count=12,
                context_key="resident_global",
            ),
        ),
        policy_version="synthetic_baseline_v1",
    )


def _baseline_with_respiration() -> BaselineSnapshot:
    movement = _baseline().features[0]
    return BaselineSnapshot(
        baseline_id="baseline_7",
        resident_id="resident_demo_a",
        monitoring_setup_version="setup_room_214_v3",
        features=(
            movement,
            FeatureBaseline(
                feature_name="respiratory_rate",
                purpose=FeaturePurpose.RESPIRATION,
                median=15.0,
                mad=0.0,
                iqr=0.0,
                lower_quantile=15.0,
                upper_quantile=15.0,
                resolution_floor=1.0,
                unit="breaths_per_min",
                eligible_sample_count=12,
                context_key="resident_global",
            ),
        ),
        policy_version="synthetic_baseline_v1",
    )


def _advance(episode, second: int, value: float | None, *, anomaly_id="anomaly_1"):
    return advance_episode(
        episode,
        frame=_frame(second, value),
        baseline=_baseline(),
        context_key="resident_global",
        anomaly_id=anomaly_id,
        policy=SyntheticAnomalyPolicy(),
    )


def _active_episode():
    update = _advance(None, 0, 14.0)
    update = _advance(update.episode, 1, 14.0)
    return _advance(update.episode, 2, 14.0)


def test_synthetic_policy_is_versioned_test_only_and_uses_fixture_values() -> None:
    # Break caught: unmarked or silently changed prototype thresholds gain authority.
    policy = SyntheticAnomalyPolicy()

    assert policy.start_abs_z == 3.0
    assert policy.end_abs_z == 1.5
    assert policy.activation_frames == 3
    assert policy.recovery_frames == 3
    assert policy.missing_grace_frames == 2
    assert policy.test_only is True
    assert policy.policy_version == "synthetic_anomaly_v1"


def test_third_consecutive_threshold_crossing_activates_one_episode() -> None:
    # Break caught: a brief two-frame change alerts, or activation is delayed past frame three.
    first = _advance(None, 0, 14.0)
    second = _advance(first.episode, 1, 14.0)
    third = _advance(second.episode, 2, 14.0)

    assert first.episode.state == AnomalyState.CANDIDATE
    assert first.episode.activation_count == 1
    assert second.episode.state == AnomalyState.CANDIDATE
    assert second.episode.activation_count == 2
    assert third.episode.state == AnomalyState.ACTIVE
    assert third.episode.activation_count == 3
    assert third.episode.anomaly_id == "anomaly_1"
    assert third.episode.candidate_started_at == _START
    assert third.episode.activated_at == _START + timedelta(seconds=3)
    assert third.episode.packet_revision == 1


def test_missing_frame_pauses_recovery_and_three_good_frames_close() -> None:
    # Break caught: absent evidence is interpreted as recovery or recovery closes too early.
    active = _active_episode().episode
    first_good = _advance(active, 3, 10.5)
    missing = _advance(first_good.episode, 4, None)
    second_good = _advance(missing.episode, 5, 10.5)
    third_good = _advance(second_good.episode, 6, 10.5)

    assert first_good.episode.state == AnomalyState.RECOVERING
    assert first_good.episode.recovery_count == 1
    assert missing.episode.state == AnomalyState.RECOVERING
    assert missing.episode.recovery_count == 1
    assert missing.episode.consecutive_missing_frames == 1
    assert second_good.episode.state == AnomalyState.RECOVERING
    assert second_good.episode.recovery_count == 2
    assert third_good.episode.state == AnomalyState.CLOSED
    assert third_good.episode.recovery_count == 3
    assert third_good.episode.closed_at == _START + timedelta(seconds=7)


def test_missing_beyond_grace_limits_evidence_but_does_not_close_episode() -> None:
    # Break caught: an extended telemetry gap either closes the anomaly or stays falsely complete.
    update = _active_episode()
    update = _advance(update.episode, 3, None)
    update = _advance(update.episode, 4, None)
    update = _advance(update.episode, 5, None)

    assert update.episode.state == AnomalyState.ACTIVE
    assert update.episode.consecutive_missing_frames == 3
    assert update.episode.recovery_count == 0
    assert update.evidence_limited is True
    assert update.limitations == ("missing_evidence_beyond_grace",)


def test_continuous_evidence_updates_revision_without_changing_id_or_prior_revision() -> None:
    # Break caught: sustained evidence creates duplicate anomalies or mutates old revisions.
    active = _active_episode().episode
    continued = _advance(active, 3, 15.0).episode

    assert active.anomaly_id == "anomaly_1"
    assert active.packet_revision == 1
    assert continued.anomaly_id == "anomaly_1"
    assert continued.packet_revision == 2
    assert continued.state == AnomalyState.ACTIVE
    with pytest.raises(FrozenInstanceError):
        active.packet_revision = 99


def test_post_recovery_recurrence_requires_new_id_and_links_closed_episode() -> None:
    # Break caught: a recovered anomaly is reopened or recurrence provenance is lost.
    update = _active_episode()
    update = _advance(update.episode, 3, 10.0)
    update = _advance(update.episode, 4, 10.0)
    closed = _advance(update.episode, 5, 10.0).episode

    recurrence = _advance(closed, 6, 14.0, anomaly_id="anomaly_2").episode

    assert closed.state == AnomalyState.CLOSED
    assert recurrence.state == AnomalyState.CANDIDATE
    assert recurrence.anomaly_id == "anomaly_2"
    assert recurrence.recurrence_of == "anomaly_1"
    assert recurrence.packet_revision == 0
    assert closed.closed_at == _START + timedelta(seconds=6)

    with pytest.raises(ValueError, match="new anomaly_id"):
        _advance(closed, 7, 14.0, anomaly_id="anomaly_1")


def test_new_extreme_feature_during_recovery_returns_episode_to_active() -> None:
    # Break caught: one feature recovers while a newly extreme feature is ignored and closes the episode.
    update = _active_episode()
    update = _advance(update.episode, 3, 10.0)
    update = _advance(update.episode, 4, 10.0)
    window_start = _START + timedelta(seconds=5)
    frame = AlignedFrame(
        frame_id="frame_new_extreme",
        window_start=window_start,
        window_end=window_start + timedelta(seconds=1),
        sources_present=("radar",),
        sources_missing=(),
        feature_evidence=(
            _feature_evidence(10.0, observation_id="movement_recovered"),
            _feature_evidence(
                19.0,
                name="respiratory_rate",
                observation_id="respiration_extreme",
                unit="breaths_per_min",
                purpose=FeaturePurpose.RESPIRATION,
            ),
        ),
        agreements=(),
        contradictions=(),
    )

    changed = advance_episode(
        update.episode,
        frame=frame,
        baseline=_baseline_with_respiration(),
        context_key="resident_global",
        anomaly_id="anomaly_1",
        policy=SyntheticAnomalyPolicy(),
    )

    assert changed.episode.state == AnomalyState.ACTIVE
    assert changed.episode.recovery_count == 0
    assert changed.episode.initiating_features == ("movement", "respiratory_rate")


def test_evidence_packet_preserves_exact_facts_versions_missingness_and_unknowns() -> None:
    # Break caught: packets omit inconvenient evidence or replace it with a semantic guess.
    active = _active_episode().episode
    evidence = (
        _feature_evidence(
            14.5,
            observation_id="observation_radar_3",
        ),
        _feature_evidence(
            13.0,
            source="thermal",
            observation_id="observation_thermal_3",
            quality=QualityClass.LIMITED,
        ),
    )
    frame = AlignedFrame(
        frame_id="frame_rich",
        window_start=_START + timedelta(seconds=3),
        window_end=_START + timedelta(seconds=4),
        sources_present=("radar", "thermal"),
        sources_missing=("wifi_csi",),
        feature_evidence=evidence,
        agreements=("presence_state:radar=thermal=present",),
        contradictions=("position_state:radar=floor_like,thermal=upright_like",),
    )
    update = advance_episode(
        active,
        frame=frame,
        baseline=_baseline(),
        context_key="resident_global",
        anomaly_id="anomaly_1",
        policy=SyntheticAnomalyPolicy(),
    )

    packet = build_evidence_packet(
        update,
        frame=frame,
        baseline=_baseline(),
        resident_id="resident_demo_a",
        room_id="room_214",
        config_version="synthetic_config_v4",
        unknowns=("cause_of_behavior_change", "wifi_csi_support"),
    )

    assert packet.anomaly_id == "anomaly_1"
    assert packet.packet_revision == 2
    assert packet.lifecycle_state == AnomalyState.ACTIVE
    assert packet.resident_id == "resident_demo_a"
    assert packet.room_id == "room_214"
    assert packet.current_time == _START + timedelta(seconds=4)
    assert packet.overall_strength == 4.5
    assert packet.strength_scale == "max_abs_robust_z"
    assert packet.progression == "sustained"
    assert tuple(
        (
            item.feature_name,
            item.source,
            item.value,
            item.unit,
            item.quality_class,
            item.baseline_median,
            item.baseline_mad,
            item.baseline_iqr,
            item.baseline_lower_quantile,
            item.baseline_upper_quantile,
            item.baseline_resolution_floor,
            item.robust_z,
        )
        for item in packet.changed_features
    ) == (
        (
            "movement",
            "radar",
            14.5,
            "normalized",
            QualityClass.GOOD,
            10.0,
            0.0,
            0.0,
            10.0,
            10.0,
            1.0,
            4.5,
        ),
        (
            "movement",
            "thermal",
            13.0,
            "normalized",
            QualityClass.LIMITED,
            10.0,
            0.0,
            0.0,
            10.0,
            10.0,
            1.0,
            3.0,
        ),
    )
    assert packet.agreements == ("presence_state:radar=thermal=present",)
    assert packet.contradictions == (
        "position_state:radar=floor_like,thermal=upright_like",
    )
    assert packet.missing_modalities == ("wifi_csi",)
    assert packet.baseline_id == "baseline_7"
    assert packet.baseline_policy_version == "synthetic_baseline_v1"
    assert packet.monitoring_setup_version == "setup_room_214_v3"
    assert packet.filter_version == "synthetic_anomaly_v1"
    assert packet.config_version == "synthetic_config_v4"
    assert packet.feature_contract_version == "1.0"
    assert packet.unknowns == ("cause_of_behavior_change", "wifi_csi_support")
    assert packet.evidence_refs == (
        "evidence://anomaly_1/2/features/movement",
    )
    assert packet.semantic_label is None
    with pytest.raises(FrozenInstanceError):
        packet.packet_revision = 3


def test_closed_episode_cannot_rebind_its_last_revision_to_a_later_frame() -> None:
    # Break caught: an immutable closed revision is reused with different later evidence.
    update = _active_episode()
    update = _advance(update.episode, 3, 10.0)
    update = _advance(update.episode, 4, 10.0)
    closed = _advance(update.episode, 5, 10.0)
    later_frame = _frame(6, 10.0)
    unchanged = advance_episode(
        closed.episode,
        frame=later_frame,
        baseline=_baseline(),
        context_key="resident_global",
        anomaly_id="anomaly_1",
        policy=SyntheticAnomalyPolicy(),
    )

    with pytest.raises(ValueError, match="revision is not bound"):
        build_evidence_packet(
            unchanged,
            frame=later_frame,
            baseline=_baseline(),
            resident_id="resident_demo_a",
            room_id="room_214",
            config_version="synthetic_config_v4",
        )


def test_acknowledgment_is_not_an_anomaly_input() -> None:
    # Break caught: caregiver workflow state begins controlling numerical recovery.
    parameters = signature(advance_episode).parameters
    assert "event_status" not in parameters
    assert "acknowledged" not in parameters
