from pathlib import Path

import pytest

from backend.app.ai.analysis_contracts import AnalysisStage
from backend.app.ai.analysis_skills import (
    analysis_skill_registry,
    fallback_specialists,
    load_analysis_skill,
)


EXPECTED_SPECIALISTS = {
    "signal_integrity",
    "movement_fall",
    "physiology",
    "inactivity_sleep",
    "presence_room",
    "routine_context",
    "repetition_escalation",
    "unknown_cross_domain",
}


def test_registry_exposes_one_recall_final_and_every_specialist_skill() -> None:
    registry = analysis_skill_registry()

    assert registry["recall_router"].stage is AnalysisStage.RECALL
    assert registry["final_integrator_reviewer"].stage is AnalysisStage.FINAL
    specialists = {
        name for name, skill in registry.items() if skill.stage is AnalysisStage.SPECIALIST
    }
    assert specialists == EXPECTED_SPECIALISTS
    assert len({skill.path for skill in registry.values()}) == len(registry)


def test_loading_a_skill_returns_versioned_bounded_instructions() -> None:
    skill = load_analysis_skill("recall_router")

    assert skill.version == "1.0"
    assert skill.path.is_file()
    assert skill.path.is_relative_to(Path("prompts/monitoring"))
    assert len(skill.instructions) > 300
    assert "raw sensor streams" in skill.instructions.lower()
    assert "evidence" in skill.instructions.lower()


@pytest.mark.parametrize("name", ("", "missing", "../core"))
def test_loading_unknown_or_unsafe_skill_name_is_rejected(name: str) -> None:
    with pytest.raises((KeyError, ValueError)):
        load_analysis_skill(name)


@pytest.mark.parametrize(
    ("families", "expected"),
    (
        (("movement",), ("signal_integrity", "movement_fall", "routine_context")),
        (("respiration",), ("signal_integrity", "physiology", "routine_context")),
        (("inactivity",), ("signal_integrity", "inactivity_sleep", "routine_context")),
        (("presence",), ("signal_integrity", "presence_room", "routine_context")),
        (("repetition",), ("signal_integrity", "repetition_escalation", "routine_context")),
        (("unknown",), ("signal_integrity", "unknown_cross_domain", "routine_context")),
    ),
)
def test_fallback_routing_uses_measured_families_without_assigning_meaning(
    families: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    assert fallback_specialists(families) == expected


def test_fallback_routing_combines_multiple_families_without_duplicates() -> None:
    assert fallback_specialists(("movement", "respiration", "movement")) == (
        "signal_integrity",
        "movement_fall",
        "physiology",
        "routine_context",
    )
