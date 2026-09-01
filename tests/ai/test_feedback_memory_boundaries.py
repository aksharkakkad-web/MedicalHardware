import pytest

from backend.app.ai.learning import MemoryUpdateAction, parse_memory_update_proposal


def _payload() -> dict[str, object]:
    return {
        "action": "add_candidate",
        "resident_id": "resident_a",
        "source_feedback_id": "feedback_1",
        "evidence_refs": ["feedback://feedback_1"],
        "confidence": 0.7,
        "context_kind": "habit",
        "description": "Sometimes reads quietly after lunch; timing is flexible.",
        "reason": "Explicit operator feedback described a repeatable benign behavior.",
        "review_after_days": 14,
    }


def test_memory_proposal_is_bounded_to_explicit_feedback_and_evidence() -> None:
    proposal = parse_memory_update_proposal(
        _payload(),
        expected_resident_id="resident_a",
        source_feedback_id="feedback_1",
        allowed_evidence_refs=("feedback://feedback_1",),
    )

    assert proposal.action == MemoryUpdateAction.ADD_CANDIDATE
    assert proposal.resident_id == "resident_a"
    assert proposal.review_after_days == 14


@pytest.mark.parametrize("protected_field", ["tenant_id", "urgent_event", "raw_measurements", "resident_identity"])
def test_memory_proposal_rejects_protected_or_unknown_fields(protected_field: str) -> None:
    payload = _payload()
    payload[protected_field] = "malicious override"

    with pytest.raises(ValueError, match="unknown or protected"):
        parse_memory_update_proposal(
            payload,
            expected_resident_id="resident_a",
            source_feedback_id="feedback_1",
            allowed_evidence_refs=("feedback://feedback_1",),
        )


def test_acknowledgment_cannot_be_used_as_feedback_source() -> None:
    with pytest.raises(ValueError, match="explicit feedback"):
        parse_memory_update_proposal(
            _payload(),
            expected_resident_id="resident_a",
            source_feedback_id="ack_event_1",
            allowed_evidence_refs=("feedback://feedback_1",),
        )
