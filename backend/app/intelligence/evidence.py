"""Immutable, bounded evidence packets for active numerical anomalies."""

from dataclasses import dataclass
from datetime import datetime

from backend.app.domain._validation import require_nonblank_text, require_strict_bool
from backend.app.intelligence.anomaly import (
    AnomalyState,
    AnomalyUpdate,
    FeatureDeviation,
)
from backend.app.intelligence.observations import _normalize_text_tuple, _require_utc
from backend.app.intelligence.baseline import BaselineSnapshot
from backend.app.intelligence.fall_detection import FallLikeAssessment
from backend.app.intelligence.fusion import AlignedFrame


def _normalize_ordered_texts(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    normalized = tuple(require_nonblank_text(item, field) for item in value)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


@dataclass(frozen=True)
class EvidencePacket:
    anomaly_id: str
    packet_revision: int
    lifecycle_state: AnomalyState
    resident_id: str
    room_id: str
    candidate_started_at: datetime
    activated_at: datetime
    current_time: datetime
    overall_strength: float | None
    strength_scale: str
    progression: str
    changed_features: tuple[FeatureDeviation, ...]
    agreements: tuple[str, ...]
    contradictions: tuple[str, ...]
    missing_modalities: tuple[str, ...]
    missing_initiating_features: tuple[str, ...]
    evidence_limited: bool
    limitations: tuple[str, ...]
    baseline_id: str
    baseline_policy_version: str
    monitoring_setup_version: str
    filter_version: str
    config_version: str
    feature_contract_version: str
    frame_id: str
    unknowns: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    semantic_label: None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in (
            "anomaly_id",
            "resident_id",
            "room_id",
            "strength_scale",
            "progression",
            "baseline_id",
            "baseline_policy_version",
            "monitoring_setup_version",
            "filter_version",
            "config_version",
            "feature_contract_version",
            "frame_id",
            "schema_version",
        ):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        if isinstance(self.packet_revision, bool) or not isinstance(
            self.packet_revision, int
        ) or self.packet_revision < 1:
            raise ValueError("packet_revision must be a positive integer")
        try:
            lifecycle = AnomalyState(self.lifecycle_state)
        except (TypeError, ValueError) as exc:
            raise ValueError("lifecycle_state must be a valid AnomalyState") from exc
        if lifecycle == AnomalyState.CANDIDATE:
            raise ValueError("candidate episodes do not produce evidence packets")
        object.__setattr__(self, "lifecycle_state", lifecycle)
        candidate_started_at = _require_utc(
            self.candidate_started_at,
            "candidate_started_at",
        )
        activated_at = _require_utc(self.activated_at, "activated_at")
        current_time = _require_utc(self.current_time, "current_time")
        if not candidate_started_at <= activated_at <= current_time:
            raise ValueError("packet timestamps must be ordered")
        object.__setattr__(self, "candidate_started_at", candidate_started_at)
        object.__setattr__(self, "activated_at", activated_at)
        object.__setattr__(self, "current_time", current_time)
        if self.overall_strength is not None:
            if isinstance(self.overall_strength, bool) or not isinstance(
                self.overall_strength,
                (int, float),
            ) or self.overall_strength < 0.0:
                raise ValueError("overall_strength must be a nonnegative number or None")
            object.__setattr__(self, "overall_strength", float(self.overall_strength))
        if not isinstance(self.changed_features, tuple) or any(
            not isinstance(item, FeatureDeviation) for item in self.changed_features
        ):
            raise ValueError("changed_features must contain FeatureDeviation records")
        for field in (
            "agreements",
            "contradictions",
            "missing_modalities",
            "missing_initiating_features",
        ):
            object.__setattr__(
                self,
                field,
                _normalize_text_tuple(getattr(self, field), field),
            )
        object.__setattr__(
            self,
            "evidence_limited",
            require_strict_bool(self.evidence_limited, "evidence_limited"),
        )
        for field in ("limitations", "unknowns", "evidence_refs"):
            object.__setattr__(
                self,
                field,
                _normalize_ordered_texts(getattr(self, field), field),
            )
        if self.semantic_label is not None:
            raise ValueError("numerical evidence packets do not assign semantic labels")


def _progression(update: AnomalyUpdate) -> str:
    episode = update.episode
    if episode is None:
        raise ValueError("an evidence packet requires an anomaly episode")
    if episode.state == AnomalyState.ACTIVE:
        return "activated" if episode.packet_revision == 1 else "sustained"
    if episode.state == AnomalyState.RECOVERING:
        return "recovering"
    if episode.state == AnomalyState.CLOSED:
        return "recovered"
    raise ValueError("candidate episodes do not produce evidence packets")


def build_evidence_packet(update: AnomalyUpdate) -> EvidencePacket:
    """Project one immutable anomaly update into its uniquely bound packet."""

    if not isinstance(update, AnomalyUpdate):
        raise ValueError("update must be an AnomalyUpdate")
    episode = update.episode
    if episode is None or episode.state == AnomalyState.CANDIDATE:
        raise ValueError("an evidence packet requires an activated anomaly")
    if (
        episode.last_frame_id != update.frame_id
        or episode.current_time != update.window_end
    ):
        raise ValueError("episode revision is not bound to this anomaly update")
    evidence_refs = tuple(
        f"evidence://{episode.anomaly_id}/{episode.packet_revision}/features/{name}"
        for name in sorted({item.feature_name for item in update.deviations})
    )
    return EvidencePacket(
        anomaly_id=episode.anomaly_id,
        packet_revision=episode.packet_revision,
        lifecycle_state=episode.state,
        resident_id=update.resident_id,
        room_id=update.room_id,
        candidate_started_at=episode.candidate_started_at,
        activated_at=episode.activated_at,
        current_time=episode.current_time,
        overall_strength=update.overall_strength,
        strength_scale="max_abs_robust_z",
        progression=_progression(update),
        changed_features=update.deviations,
        agreements=update.agreements,
        contradictions=update.contradictions,
        missing_modalities=update.missing_sources,
        missing_initiating_features=update.missing_initiating_features,
        evidence_limited=update.evidence_limited,
        limitations=update.limitations,
        baseline_id=update.baseline_id,
        baseline_policy_version=update.baseline_policy_version,
        monitoring_setup_version=update.monitoring_setup_version,
        filter_version=update.filter_version,
        config_version=update.config_version,
        feature_contract_version=update.feature_contract_version,
        frame_id=update.frame_id,
        unknowns=update.unknowns,
        evidence_refs=evidence_refs,
    )


def build_fall_evidence_packet(
    assessment: FallLikeAssessment,
    *,
    frame: AlignedFrame,
    baseline: BaselineSnapshot,
    anomaly_id: str,
    packet_revision: int,
    config_version: str,
    unknowns: tuple[str, ...],
) -> EvidencePacket:
    """Project a confirmed deterministic fall-like pattern into AI evidence."""

    if not assessment.urgent_triggered or assessment.transition_started_at is None:
        raise ValueError("fall evidence requires a confirmed fall-like assessment")
    if frame.resident_id != baseline.resident_id:
        raise ValueError("fall evidence baseline resident does not match frame")
    refs = tuple(
        f"evidence://{anomaly_id}/{packet_revision}/fall-like/{index}"
        for index, _ in enumerate(assessment.evidence, start=1)
    )
    if not refs:
        refs = (f"evidence://{anomaly_id}/{packet_revision}/fall-like/state",)
    return EvidencePacket(
        anomaly_id=anomaly_id,
        packet_revision=packet_revision,
        lifecycle_state=AnomalyState.ACTIVE,
        resident_id=frame.resident_id,
        room_id=frame.room_id,
        candidate_started_at=assessment.transition_started_at,
        activated_at=assessment.assessed_at,
        current_time=assessment.assessed_at,
        overall_strength=None,
        strength_scale="fall_like_state_machine",
        progression="activated",
        changed_features=(),
        agreements=assessment.evidence,
        contradictions=assessment.contradictions,
        missing_modalities=assessment.missing_sources,
        missing_initiating_features=(),
        evidence_limited=bool(assessment.limitations),
        limitations=tuple(
            dict.fromkeys(
                (
                    *assessment.limitations,
                    "synthetic fall-like policy; not a clinical diagnosis",
                )
            )
        ),
        baseline_id=baseline.baseline_id,
        baseline_policy_version=baseline.policy_version,
        monitoring_setup_version=baseline.monitoring_setup_version,
        filter_version=assessment.policy_version,
        config_version=config_version,
        feature_contract_version="1.0",
        frame_id=frame.frame_id,
        unknowns=unknowns,
        evidence_refs=refs,
    )


__all__ = [
    "EvidencePacket",
    "build_evidence_packet",
    "build_fall_evidence_packet",
]
