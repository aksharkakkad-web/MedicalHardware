"""Immutable, bounded evidence packets for active numerical anomalies."""

from dataclasses import dataclass
from datetime import datetime

from backend.app.domain._validation import require_nonblank_text, require_strict_bool
from backend.app.intelligence.anomaly import (
    AnomalyState,
    AnomalyUpdate,
    FeatureDeviation,
)
from backend.app.intelligence.baseline import BaselineSnapshot
from backend.app.intelligence.fusion import AlignedFrame
from backend.app.intelligence.observations import _normalize_text_tuple, _require_utc


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
    overall_strength: float
    strength_scale: str
    progression: str
    changed_features: tuple[FeatureDeviation, ...]
    agreements: tuple[str, ...]
    contradictions: tuple[str, ...]
    missing_modalities: tuple[str, ...]
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
        if isinstance(self.overall_strength, bool) or not isinstance(
            self.overall_strength,
            (int, float),
        ) or self.overall_strength < 0.0:
            raise ValueError("overall_strength must be a nonnegative number")
        object.__setattr__(self, "overall_strength", float(self.overall_strength))
        if not isinstance(self.changed_features, tuple) or any(
            not isinstance(item, FeatureDeviation) for item in self.changed_features
        ):
            raise ValueError("changed_features must contain FeatureDeviation records")
        for field in ("agreements", "contradictions", "missing_modalities"):
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


def build_evidence_packet(
    update: AnomalyUpdate,
    *,
    frame: AlignedFrame,
    baseline: BaselineSnapshot,
    resident_id: str,
    room_id: str,
    config_version: str,
    unknowns: tuple[str, ...] = ("cause_of_behavior_change",),
) -> EvidencePacket:
    """Bind one anomaly revision to its exact frame, baseline, and unknowns."""

    if not isinstance(update, AnomalyUpdate):
        raise ValueError("update must be an AnomalyUpdate")
    if not isinstance(frame, AlignedFrame):
        raise ValueError("frame must be an AlignedFrame")
    if not isinstance(baseline, BaselineSnapshot):
        raise ValueError("baseline must be a BaselineSnapshot")
    episode = update.episode
    if episode is None or episode.state == AnomalyState.CANDIDATE:
        raise ValueError("an evidence packet requires an activated anomaly")
    resident = require_nonblank_text(resident_id, "resident_id")
    room = require_nonblank_text(room_id, "room_id")
    config = require_nonblank_text(config_version, "config_version")
    explicit_unknowns = _normalize_ordered_texts(unknowns, "unknowns")
    if not explicit_unknowns:
        raise ValueError("unknowns must state at least one unresolved fact")
    if baseline.resident_id != resident:
        raise ValueError("baseline resident must match evidence resident")
    if (
        update.frame_id != frame.frame_id
        or update.window_start != frame.window_start
        or update.window_end != frame.window_end
    ):
        raise ValueError("frame must match the anomaly update's bound frame")
    if (
        episode.last_frame_id != update.frame_id
        or episode.current_time != update.window_end
    ):
        raise ValueError("episode revision is not bound to this anomaly update")
    if (
        update.baseline_id != baseline.baseline_id
        or update.baseline_policy_version != baseline.policy_version
        or update.monitoring_setup_version != baseline.monitoring_setup_version
    ):
        raise ValueError("baseline must match the anomaly update's bound baseline")
    evidence_refs = tuple(
        f"evidence://{episode.anomaly_id}/{episode.packet_revision}/features/{name}"
        for name in sorted({item.feature_name for item in update.deviations})
    )
    return EvidencePacket(
        anomaly_id=episode.anomaly_id,
        packet_revision=episode.packet_revision,
        lifecycle_state=episode.state,
        resident_id=resident,
        room_id=room,
        candidate_started_at=episode.candidate_started_at,
        activated_at=episode.activated_at,
        current_time=episode.current_time,
        overall_strength=update.overall_strength,
        strength_scale="max_abs_robust_z",
        progression=_progression(update),
        changed_features=update.deviations,
        agreements=frame.agreements,
        contradictions=frame.contradictions,
        missing_modalities=frame.sources_missing,
        evidence_limited=update.evidence_limited,
        limitations=update.limitations,
        baseline_id=baseline.baseline_id,
        baseline_policy_version=baseline.policy_version,
        monitoring_setup_version=baseline.monitoring_setup_version,
        filter_version=update.policy_version,
        config_version=config,
        feature_contract_version=frame.schema_version,
        frame_id=frame.frame_id,
        unknowns=explicit_unknowns,
        evidence_refs=evidence_refs,
    )


__all__ = ["EvidencePacket", "build_evidence_packet"]
