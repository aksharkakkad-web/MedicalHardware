from backend.app.ai.skills import load_skill


def test_feedback_and_memory_skills_are_registered_and_versioned() -> None:
    feedback_version, feedback = load_skill("feedback_agent")
    memory_version, memory = load_skill("resident_memory_updater")

    assert feedback_version == "feedback_agent_v1"
    assert memory_version == "resident_memory_updater_v1"
    assert "Acknowledgment is not feedback" in feedback
    assert "explicit operator feedback" in feedback
    assert "reversible" in memory
    assert "protected" in memory
    assert "no_change" in memory


def test_learning_skills_never_authorize_direct_safety_or_identity_changes() -> None:
    combined = "\n".join(load_skill(name)[1] for name in ("feedback_agent", "resident_memory_updater"))

    assert "Do not suppress" in combined
    assert "tenant" in combined
    assert "resident identity" in combined
    assert "raw measurement" in combined
