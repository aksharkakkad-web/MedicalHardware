from datetime import datetime, timedelta, timezone

import pytest

from backend.app.domain.events import EventPriority, EventStore, ResolutionOutcome
from backend.app.domain.feedback import FeedbackService, ResidentMemoryService


STARTED_AT = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)


def _feedback_memory():
    events = EventStore()
    event = events.record_signal(
        resident_id="resident_demo_a",
        room_id="room_214",
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority=EventPriority.HIGH,
        observed_at=STARTED_AT,
    )
    events.acknowledge(
        event.event_id,
        actor_id="operator_1",
        at=STARTED_AT + timedelta(minutes=1),
    )
    events.check(
        event.event_id,
        actor_id="operator_1",
        at=STARTED_AT + timedelta(minutes=2),
    )
    resolved = events.resolve(
        event.event_id,
        ResolutionOutcome.FALSE_POSITIVE,
        actor_id="operator_1",
        at=STARTED_AT + timedelta(minutes=3),
    )
    return FeedbackService().submit_feedback(
        event=resolved,
        actor_id="operator_1",
        actual_event_label="assisted_transfer",
        routine=True,
        created_at=STARTED_AT + timedelta(minutes=4),
    ).memory


def test_feedback_created_memory_has_explicit_feedback_provenance() -> None:
    entry = _feedback_memory().entries[0]

    assert entry.source_kind == "feedback"
    assert entry.source_feedback_id is not None
    assert entry.supersedes_entry_id is None


def test_operator_can_add_memory_at_expected_version_zero() -> None:
    memory = ResidentMemoryService().add_entry(
        resident_id="resident_demo_a",
        expected_version=0,
        description="Assisted standing is common before breakfast.",
        actor_id="operator_1",
        changed_at=STARTED_AT,
    )

    assert memory.version == 1
    assert len(memory.active_entries) == 1
    entry = memory.active_entries[0]
    assert entry.description == "Assisted standing is common before breakfast."
    assert entry.source_kind == "operator"
    assert entry.source_feedback_id is None
    assert entry.supersedes_entry_id is None


def test_operator_add_appends_a_version_without_mutating_previous_snapshot() -> None:
    first = ResidentMemoryService().add_entry(
        resident_id="resident_demo_a",
        expected_version=0,
        description="Morning assisted standing.",
        actor_id="operator_1",
        changed_at=STARTED_AT,
    )
    service = ResidentMemoryService(initial_memories=(first,))

    second = service.add_entry(
        resident_id="resident_demo_a",
        expected_version=1,
        description="Evening assisted standing.",
        actor_id="operator_2",
        changed_at=STARTED_AT + timedelta(minutes=5),
    )

    assert second.version == 2
    assert [entry.description for entry in second.entries] == [
        "Morning assisted standing.",
        "Evening assisted standing.",
    ]
    assert first.version == 1
    assert [entry.description for entry in first.entries] == [
        "Morning assisted standing."
    ]


def test_operator_memory_commands_reject_stale_expected_version() -> None:
    first = ResidentMemoryService().add_entry(
        resident_id="resident_demo_a",
        expected_version=0,
        description="Morning assisted standing.",
        actor_id="operator_1",
        changed_at=STARTED_AT,
    )
    service = ResidentMemoryService(initial_memories=(first,))

    with pytest.raises(ValueError, match="expected_version"):
        service.add_entry(
            resident_id="resident_demo_a",
            expected_version=0,
            description="Stale overwrite.",
            actor_id="operator_2",
            changed_at=STARTED_AT + timedelta(minutes=1),
        )

    assert service.current_memory("resident_demo_a") == first


def test_operator_correction_retires_target_and_creates_linked_replacement() -> None:
    original = _feedback_memory()
    target = original.active_entries[0]
    service = ResidentMemoryService(initial_memories=(original,))
    corrected_at = STARTED_AT + timedelta(minutes=10)

    corrected = service.correct_entry(
        resident_id="resident_demo_a",
        entry_id=target.entry_id,
        expected_version=1,
        description="Assisted standing is common after breakfast.",
        reason="The routine time was entered incorrectly.",
        actor_id="operator_2",
        changed_at=corrected_at,
    )

    assert corrected.version == 2
    assert len(corrected.entries) == 2
    retired, replacement = corrected.entries
    assert retired.entry_id == target.entry_id
    assert retired.status == "retired"
    assert retired.retired_by == "operator_2"
    assert retired.retired_at == corrected_at
    assert retired.retirement_reason == "The routine time was entered incorrectly."
    assert replacement.status == "active"
    assert replacement.description == "Assisted standing is common after breakfast."
    assert replacement.source_kind == "operator"
    assert replacement.source_feedback_id is None
    assert replacement.supersedes_entry_id == target.entry_id
    assert original.entries == (target,)
    assert original.entries[0].status == "active"


def test_operator_retirement_creates_no_replacement() -> None:
    original = _feedback_memory()
    service = ResidentMemoryService(initial_memories=(original,))

    retired = service.retire_entry(
        resident_id="resident_demo_a",
        entry_id=original.active_entries[0].entry_id,
        expected_version=1,
        reason="This routine is no longer current.",
        actor_id="operator_2",
        changed_at=STARTED_AT + timedelta(minutes=10),
    )

    assert retired.version == 2
    assert len(retired.entries) == 1
    assert retired.active_entries == ()
    assert retired.entries[0].status == "retired"
    assert retired.entries[0].supersedes_entry_id is None


def test_memory_history_cannot_move_backward_in_time() -> None:
    original = _feedback_memory()
    service = ResidentMemoryService(initial_memories=(original,))

    with pytest.raises(ValueError, match="changed_at"):
        service.add_entry(
            resident_id="resident_demo_a",
            expected_version=1,
            description="Earlier change.",
            actor_id="operator_2",
            changed_at=STARTED_AT + timedelta(minutes=3),
        )

    assert service.current_memory("resident_demo_a") == original


def test_retired_memory_cannot_be_corrected_or_retired_again() -> None:
    original = _feedback_memory()
    service = ResidentMemoryService(initial_memories=(original,))
    entry_id = original.active_entries[0].entry_id
    retired = service.retire_entry(
        resident_id="resident_demo_a",
        entry_id=entry_id,
        expected_version=1,
        reason="No longer current.",
        actor_id="operator_2",
        changed_at=STARTED_AT + timedelta(minutes=10),
    )

    for command in (
        lambda: service.correct_entry(
            resident_id="resident_demo_a",
            entry_id=entry_id,
            expected_version=retired.version,
            description="Replacement.",
            reason="Correction.",
            actor_id="operator_3",
            changed_at=STARTED_AT + timedelta(minutes=11),
        ),
        lambda: service.retire_entry(
            resident_id="resident_demo_a",
            entry_id=entry_id,
            expected_version=retired.version,
            reason="Retire again.",
            actor_id="operator_3",
            changed_at=STARTED_AT + timedelta(minutes=11),
        ),
    ):
        with pytest.raises(ValueError, match="active"):
            command()

    assert service.current_memory("resident_demo_a") == retired


@pytest.mark.parametrize(
    ("command", "field"),
    (
        ("add", "description"),
        ("correct_description", "description"),
        ("correct_reason", "reason"),
        ("retire", "reason"),
    ),
)
def test_operator_memory_commands_require_nonblank_text(
    command: str,
    field: str,
) -> None:
    original = _feedback_memory()
    service = ResidentMemoryService(initial_memories=(original,))
    common = {
        "resident_id": "resident_demo_a",
        "expected_version": 1,
        "actor_id": "operator_2",
        "changed_at": STARTED_AT + timedelta(minutes=10),
    }

    with pytest.raises(ValueError, match=field):
        if command == "add":
            service.add_entry(description="   ", **common)
        elif command == "correct_description":
            service.correct_entry(
                entry_id=original.active_entries[0].entry_id,
                description="   ",
                reason="Correction.",
                **common,
            )
        elif command == "correct_reason":
            service.correct_entry(
                entry_id=original.active_entries[0].entry_id,
                description="Replacement.",
                reason="   ",
                **common,
            )
        else:
            service.retire_entry(
                entry_id=original.active_entries[0].entry_id,
                reason="   ",
                **common,
            )
