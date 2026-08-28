"""Deterministic alignment of normalized evidence without score averaging."""

from dataclasses import dataclass
from datetime import datetime
from itertools import groupby

from backend.app.domain._validation import require_nonblank_text
from backend.app.intelligence.observations import (
    FeatureValue,
    NormalizedObservation,
    _normalize_text_tuple,
    _require_utc,
)


def _value_key(value: object) -> tuple[str, str]:
    return type(value).__name__, repr(value)


@dataclass(frozen=True)
class FeatureEvidence:
    source: str
    observation_id: str
    feature: FeatureValue

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", require_nonblank_text(self.source, "source"))
        object.__setattr__(
            self,
            "observation_id",
            require_nonblank_text(self.observation_id, "observation_id"),
        )
        if not isinstance(self.feature, FeatureValue):
            raise ValueError("feature must be a FeatureValue")


@dataclass(frozen=True)
class AlignedFrame:
    frame_id: str
    window_start: datetime
    window_end: datetime
    sources_present: tuple[str, ...]
    sources_missing: tuple[str, ...]
    feature_evidence: tuple[FeatureEvidence, ...]
    agreements: tuple[str, ...]
    contradictions: tuple[str, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame_id", require_nonblank_text(self.frame_id, "frame_id"))
        window_start = _require_utc(self.window_start, "window_start")
        window_end = _require_utc(self.window_end, "window_end")
        if window_end <= window_start:
            raise ValueError("window_end must be after window_start")
        object.__setattr__(self, "window_start", window_start)
        object.__setattr__(self, "window_end", window_end)
        sources_present = _normalize_text_tuple(self.sources_present, "sources_present")
        sources_missing = _normalize_text_tuple(self.sources_missing, "sources_missing")
        if set(sources_present) & set(sources_missing):
            raise ValueError("sources_present and sources_missing must not overlap")
        object.__setattr__(self, "sources_present", sources_present)
        object.__setattr__(self, "sources_missing", sources_missing)
        if not isinstance(self.feature_evidence, tuple):
            raise ValueError("feature_evidence must be a tuple")
        if any(
            not isinstance(evidence, FeatureEvidence)
            for evidence in self.feature_evidence
        ):
            raise ValueError("feature_evidence must contain FeatureEvidence records")
        object.__setattr__(
            self,
            "feature_evidence",
            tuple(
                sorted(
                    self.feature_evidence,
                    key=lambda evidence: (
                        evidence.feature.name,
                        evidence.feature.unit,
                        evidence.source,
                        evidence.observation_id,
                    ),
                )
            ),
        )
        object.__setattr__(self, "agreements", _normalize_text_tuple(self.agreements, "agreements"))
        object.__setattr__(
            self,
            "contradictions",
            _normalize_text_tuple(self.contradictions, "contradictions"),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_nonblank_text(self.schema_version, "schema_version"),
        )


def _agreement_records(evidence: tuple[FeatureEvidence, ...]) -> tuple[str, ...]:
    records: list[str] = []
    grouped = groupby(
        sorted(
            evidence,
            key=lambda item: (
                item.feature.name,
                item.feature.unit,
                *_value_key(item.feature.value),
                item.source,
            ),
        ),
        key=lambda item: (
            item.feature.name,
            item.feature.unit,
            _value_key(item.feature.value),
        ),
    )
    for (name, _unit, _value), items in grouped:
        independent = tuple(sorted(items, key=lambda item: item.source))
        value = independent[0].feature.value
        if value is not None and len({item.source for item in independent}) > 1:
            sources = "=".join(sorted({item.source for item in independent}))
            records.append(f"{name}:{sources}={value}")
    return tuple(records)


def _contradiction_records(evidence: tuple[FeatureEvidence, ...]) -> tuple[str, ...]:
    records: list[str] = []
    categorical = tuple(item for item in evidence if isinstance(item.feature.value, str))
    grouped = groupby(categorical, key=lambda item: item.feature.name)
    for name, items in grouped:
        independent = tuple(sorted(items, key=lambda item: item.source))
        values = {item.feature.value for item in independent}
        if len(values) > 1:
            descriptions = ",".join(
                f"{item.source}={item.feature.value}" for item in independent
            )
            records.append(f"{name}:{descriptions}")
    return tuple(records)


def align_observations(
    observations: tuple[NormalizedObservation, ...],
    *,
    frame_id: str,
    window_start: datetime,
    window_end: datetime,
    expected_sources: tuple[str, ...],
) -> AlignedFrame:
    """Align one target window while preserving each source's evidence."""

    if not isinstance(observations, tuple):
        raise ValueError("observations must be a tuple")
    if any(not isinstance(observation, NormalizedObservation) for observation in observations):
        raise ValueError("observations must contain NormalizedObservation records")
    frame_window_start = _require_utc(window_start, "window_start")
    frame_window_end = _require_utc(window_end, "window_end")
    if frame_window_end <= frame_window_start:
        raise ValueError("window_end must be after window_start")
    expected = _normalize_text_tuple(expected_sources, "expected_sources")
    for observation in observations:
        if (
            observation.window_start < frame_window_start
            or observation.window_end > frame_window_end
        ):
            raise ValueError("observation window must fall within frame window")
    sources_present = tuple(sorted({observation.source for observation in observations}))
    sources_missing = tuple(sorted(set(expected) - set(sources_present)))
    evidence = tuple(
        sorted(
            (
                FeatureEvidence(
                    source=observation.source,
                    observation_id=observation.observation_id,
                    feature=feature,
                )
                for observation in observations
                for feature in observation.features
            ),
            key=lambda item: (
                item.feature.name,
                item.feature.unit,
                item.source,
                item.observation_id,
            ),
        )
    )
    return AlignedFrame(
        frame_id=frame_id,
        window_start=frame_window_start,
        window_end=frame_window_end,
        sources_present=sources_present,
        sources_missing=sources_missing,
        feature_evidence=evidence,
        agreements=_agreement_records(evidence),
        contradictions=_contradiction_records(evidence),
    )


__all__ = ["AlignedFrame", "FeatureEvidence", "align_observations"]
