"""Operational monitoring-degradation assessment, separate from anomalies."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from backend.app.domain._validation import (
    coerce_enum,
    require_nonblank_text,
    require_strict_bool,
)
from backend.app.intelligence.fusion import AlignedFrame, FeatureEvidence
from backend.app.intelligence.observations import _normalize_text_tuple, _require_utc


class DegradationKind(StrEnum):
    DEVICE_MOVEMENT = "device_movement"
    ENVIRONMENT_SHIFT = "environment_shift"
    FROZEN_SIGNAL = "frozen_signal"
    STALE_SIGNAL = "stale_signal"


@dataclass(frozen=True)
class DegradationAssessment:
    frame_id: str
    assessed_at: datetime
    degraded: bool
    kinds: tuple[DegradationKind, ...]
    evidence: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    contradictions: tuple[str, ...]
    missing_sources: tuple[str, ...]
    assessment_scope: str
    resident_anomaly: bool
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame_id", require_nonblank_text(self.frame_id, "frame_id"))
        object.__setattr__(self, "assessed_at", _require_utc(self.assessed_at, "assessed_at"))
        object.__setattr__(self, "degraded", require_strict_bool(self.degraded, "degraded"))
        if not isinstance(self.kinds, tuple):
            raise ValueError("kinds must be a tuple")
        normalized_kinds = tuple(
            sorted(
                (coerce_enum(kind, DegradationKind, "kinds") for kind in self.kinds),
                key=str,
            )
        )
        if len(set(normalized_kinds)) != len(normalized_kinds):
            raise ValueError("kinds must not contain duplicates")
        object.__setattr__(self, "kinds", normalized_kinds)
        if self.degraded != bool(normalized_kinds):
            raise ValueError("degraded must reflect whether degradation kinds exist")
        for field in (
            "evidence",
            "evidence_sources",
            "contradictions",
            "missing_sources",
        ):
            object.__setattr__(
                self,
                field,
                _normalize_text_tuple(getattr(self, field), field),
            )
        scope = require_nonblank_text(self.assessment_scope, "assessment_scope")
        if scope != "operational":
            raise ValueError("assessment_scope must be operational")
        object.__setattr__(self, "assessment_scope", scope)
        resident_anomaly = require_strict_bool(
            self.resident_anomaly,
            "resident_anomaly",
        )
        if resident_anomaly:
            raise ValueError("monitoring degradation cannot be a resident anomaly")
        object.__setattr__(self, "resident_anomaly", resident_anomaly)
        object.__setattr__(
            self,
            "schema_version",
            require_nonblank_text(self.schema_version, "schema_version"),
        )


def _evidence_text(item: FeatureEvidence) -> str:
    return (
        f"{item.source}:{item.observation_id}:{item.feature.name}="
        f"{item.feature.value} {item.feature.unit}"
    )


def assess_monitoring_degradation(frame: AlignedFrame) -> DegradationAssessment:
    """Classify explicit sensor/setup failure evidence without resident inference."""

    if not isinstance(frame, AlignedFrame):
        raise ValueError("frame must be an AlignedFrame")
    matches: list[tuple[DegradationKind, FeatureEvidence]] = []
    for item in frame.feature_evidence:
        reasons = set(item.feature.quality_reasons)
        if "stale" in reasons:
            matches.append((DegradationKind.STALE_SIGNAL, item))
        if "frozen" in reasons:
            matches.append((DegradationKind.FROZEN_SIGNAL, item))
        if item.feature.name == "device_moved" and item.feature.value is True:
            matches.append((DegradationKind.DEVICE_MOVEMENT, item))
        if item.feature.name == "environment_shift" and item.feature.value is True:
            matches.append((DegradationKind.ENVIRONMENT_SHIFT, item))

    kinds = tuple(sorted({kind for kind, _item in matches}, key=str))
    matched_items = tuple(
        sorted(
            {item for _kind, item in matches},
            key=lambda item: (
                item.source,
                item.observation_id,
                item.feature.name,
                item.feature.unit,
            ),
        )
    )
    return DegradationAssessment(
        frame_id=frame.frame_id,
        assessed_at=frame.window_end,
        degraded=bool(kinds),
        kinds=kinds,
        evidence=tuple(_evidence_text(item) for item in matched_items),
        evidence_sources=tuple(sorted({item.source for item in matched_items})),
        contradictions=frame.contradictions,
        missing_sources=frame.sources_missing,
        assessment_scope="operational",
        resident_anomaly=False,
    )


__all__ = [
    "DegradationAssessment",
    "DegradationKind",
    "assess_monitoring_degradation",
]
