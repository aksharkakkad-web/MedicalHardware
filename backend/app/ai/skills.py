"""Explicit registry and deterministic selection for monitoring skills."""

from dataclasses import dataclass
from pathlib import Path

from backend.app.intelligence.evidence import EvidencePacket


_PROMPT_ROOT = Path(__file__).resolve().parents[3] / "prompts" / "monitoring"
_SKILL_REGISTRY = {
    "core": ("core.md", "core_v1"),
    "fall_like": ("fall_like.md", "fall_like_v1"),
    "inactivity": ("inactivity.md", "inactivity_v1"),
    "movement": ("movement.md", "movement_v1"),
    "respiration": ("respiration.md", "respiration_v1"),
    "routine_change": ("routine_change.md", "routine_change_v1"),
    "monitoring_degraded": ("monitoring_degraded.md", "monitoring_degraded_v1"),
    "multi_person": ("multi_person.md", "multi_person_v1"),
    "unknown_anomaly": ("unknown_anomaly.md", "unknown_anomaly_v1"),
}


@dataclass(frozen=True)
class SkillBundle:
    skill_names: tuple[str, ...]
    skill_versions: tuple[str, ...]
    prompt: str
    bundle_version: str = "monitoring_skills_v1"


def load_skill(name: str) -> tuple[str, str]:
    """Load one registered skill; caller-controlled paths are never accepted."""

    try:
        relative_path, version = _SKILL_REGISTRY[name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unknown monitoring skill: {name}") from exc
    root = _PROMPT_ROOT.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"monitoring skill escapes prompt root: {name}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"monitoring skill is empty: {name}")
    return version, content


def _primary_skill(packet: EvidencePacket) -> str:
    names = {item.feature_name.casefold() for item in packet.changed_features}
    if any(
        marker in name
        for name in names
        for marker in (
            "fall",
            "descent",
            "height_drop",
            "floor_position",
            "rapid_downward",
        )
    ):
        return "fall_like"
    if any("inactivity" in name or "no_movement" in name for name in names):
        return "inactivity"
    if any("respirat" in name or "breath" in name for name in names):
        return "respiration"
    if any("routine" in name or "habit" in name for name in names):
        return "routine_change"
    if any(
        marker in name
        for name in names
        for marker in ("movement", "motion", "velocity", "position", "activity")
    ):
        return "movement"
    if packet.evidence_limited and not packet.changed_features:
        return "monitoring_degraded"
    return "unknown_anomaly"


def _has_multi_person_ambiguity(packet: EvidencePacket) -> bool:
    records = (
        *packet.agreements,
        *packet.contradictions,
        *packet.limitations,
        *packet.unknowns,
    )
    normalized = " ".join(records).casefold().replace("-", "_")
    return "multi_person" in normalized or "multiple_people" in normalized


def select_skill_bundle(packet: EvidencePacket) -> SkillBundle:
    if not isinstance(packet, EvidencePacket):
        raise ValueError("packet must be an EvidencePacket")
    names = ["core", _primary_skill(packet)]
    if _has_multi_person_ambiguity(packet):
        names.append("multi_person")
    loaded = tuple(load_skill(name) for name in names)
    return SkillBundle(
        skill_names=tuple(names),
        skill_versions=tuple(version for version, _content in loaded),
        prompt="\n\n---\n\n".join(content for _version, content in loaded),
    )


__all__ = ["SkillBundle", "load_skill", "select_skill_bundle"]
