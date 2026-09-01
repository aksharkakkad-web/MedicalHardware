"""Versioned skill registry for multi-stage monitoring analysis."""

from dataclasses import dataclass
from pathlib import Path

from backend.app.ai.analysis_contracts import AnalysisStage


_ROOT = Path("prompts/monitoring")
_DECLARATIONS = {
    "recall_router": (AnalysisStage.RECALL, "recall_router.md"),
    "signal_integrity": (AnalysisStage.SPECIALIST, "specialists/signal_integrity.md"),
    "movement_fall": (AnalysisStage.SPECIALIST, "specialists/movement_fall.md"),
    "physiology": (AnalysisStage.SPECIALIST, "specialists/physiology.md"),
    "inactivity_sleep": (AnalysisStage.SPECIALIST, "specialists/inactivity_sleep.md"),
    "presence_room": (AnalysisStage.SPECIALIST, "specialists/presence_room.md"),
    "routine_context": (AnalysisStage.SPECIALIST, "specialists/routine_context.md"),
    "repetition_escalation": (AnalysisStage.SPECIALIST, "specialists/repetition_escalation.md"),
    "unknown_cross_domain": (AnalysisStage.SPECIALIST, "specialists/unknown_cross_domain.md"),
    "final_integrator_reviewer": (AnalysisStage.FINAL, "final_integrator_reviewer.md"),
}
_FAMILY_SPECIALIST = {
    "movement": "movement_fall",
    "fall_like": "movement_fall",
    "respiration": "physiology",
    "physiology": "physiology",
    "inactivity": "inactivity_sleep",
    "sleep": "inactivity_sleep",
    "presence": "presence_room",
    "away": "presence_room",
    "repetition": "repetition_escalation",
    "recurrence": "repetition_escalation",
    "unknown": "unknown_cross_domain",
}


@dataclass(frozen=True)
class AnalysisSkill:
    name: str
    stage: AnalysisStage
    version: str
    path: Path
    instructions: str


def load_analysis_skill(name: str) -> AnalysisSkill:
    if not isinstance(name, str) or not name or name not in _DECLARATIONS:
        raise KeyError(f"Unknown analysis skill: {name!r}")
    stage, relative = _DECLARATIONS[name]
    path = _ROOT / relative
    instructions = path.read_text(encoding="utf-8").strip()
    if not instructions:
        raise ValueError(f"Analysis skill is empty: {name}")
    return AnalysisSkill(
        name=name,
        stage=stage,
        version="1.0",
        path=path,
        instructions=instructions,
    )


def analysis_skill_registry() -> dict[str, AnalysisSkill]:
    return {name: load_analysis_skill(name) for name in _DECLARATIONS}


def fallback_specialists(anomaly_families: tuple[str, ...]) -> tuple[str, ...]:
    """Route by measured family only; this function does not interpret meaning."""

    if not isinstance(anomaly_families, tuple):
        raise ValueError("anomaly_families must be a tuple")
    routed = ["signal_integrity"]
    for family in anomaly_families:
        if not isinstance(family, str) or not family.strip():
            raise ValueError("anomaly_families must contain nonblank text")
        specialist = _FAMILY_SPECIALIST.get(family.strip(), "unknown_cross_domain")
        if specialist not in routed:
            routed.append(specialist)
    if len(routed) == 1:
        routed.append("unknown_cross_domain")
    routed.append("routine_context")
    return tuple(dict.fromkeys(routed))


__all__ = [
    "AnalysisSkill",
    "analysis_skill_registry",
    "fallback_specialists",
    "load_analysis_skill",
]
