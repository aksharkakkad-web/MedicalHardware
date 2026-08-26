"""Trusted operator feedback and versioned resident context for toy scenarios."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from backend.app.domain.events import EventStatus, MonitoringEvent, ResolutionOutcome


def _require_text(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string")


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")


@dataclass(frozen=True)
class FeedbackRecord:
    feedback_id: str
    event_id: str
    resident_id: str
    actor_id: str
    outcome: ResolutionOutcome
    actual_event_label: str
    routine: bool
    created_at: datetime


@dataclass(frozen=True)
class MemoryEntry:
    entry_id: str
    description: str
    source_feedback_id: str
    status: str
    created_by: str
    created_at: datetime
    retired_by: str | None = None
    retired_at: datetime | None = None
    retirement_reason: str | None = None


@dataclass(frozen=True)
class ResidentMemory:
    resident_id: str
    version: int
    entries: tuple[MemoryEntry, ...]

    @property
    def active_entries(self) -> tuple[MemoryEntry, ...]:
        return tuple(entry for entry in self.entries if entry.status == "active")


@dataclass(frozen=True)
class LearningDecision:
    feedback: FeedbackRecord
    memory: ResidentMemory
    memory_updated: bool
    baseline_window_eligible: bool
    global_label_recorded: bool


class FeedbackService:
    def __init__(self) -> None:
        self._memories: dict[str, ResidentMemory] = {}
        self._feedback: dict[str, FeedbackRecord] = {}

    def submit_feedback(
        self,
        *,
        event: MonitoringEvent,
        actor_id: str,
        actual_event_label: str,
        routine: bool,
        created_at: datetime,
    ) -> LearningDecision:
        if event.status != EventStatus.RESOLVED or event.resolution_outcome is None:
            raise ValueError("feedback requires a resolved event")
        _require_text(actor_id, "actor_id")
        _require_text(actual_event_label, "actual_event_label")
        if type(routine) is not bool:
            raise ValueError("routine must be a boolean")
        _require_aware(created_at, "created_at")
        _require_aware(event.last_signal_at, "event timestamp")
        if created_at < event.last_signal_at:
            raise ValueError("created_at cannot precede the event timestamp")

        feedback = FeedbackRecord(
            feedback_id=f"fb_{uuid4().hex}",
            event_id=event.event_id,
            resident_id=event.resident_id,
            actor_id=actor_id,
            outcome=event.resolution_outcome,
            actual_event_label=actual_event_label,
            routine=routine,
            created_at=created_at,
        )
        self._feedback[feedback.feedback_id] = feedback

        memory = self._memories.get(event.resident_id, ResidentMemory(event.resident_id, 0, ()))
        memory_updated = bool(routine and actual_event_label != "unknown")
        if memory_updated:
            entry = MemoryEntry(
                entry_id=f"memory_{uuid4().hex}",
                description=actual_event_label,
                source_feedback_id=feedback.feedback_id,
                status="active",
                created_by=actor_id,
                created_at=created_at,
            )
            memory = ResidentMemory(event.resident_id, memory.version + 1, memory.entries + (entry,))
            self._memories[event.resident_id] = memory

        baseline_window_eligible = event.resolution_outcome == ResolutionOutcome.FALSE_POSITIVE and routine
        return LearningDecision(feedback, memory, memory_updated, baseline_window_eligible, True)

    def correct_memory(
        self,
        *,
        resident_id: str,
        entry_id: str,
        actor_id: str,
        reason: str,
        corrected_at: datetime,
    ) -> ResidentMemory:
        _require_text(actor_id, "actor_id")
        _require_text(reason, "reason")
        _require_aware(corrected_at, "corrected_at")
        memory = self._memories[resident_id]
        target = next((entry for entry in memory.entries if entry.entry_id == entry_id), None)
        if target is None:
            raise KeyError(f"Unknown memory entry: {entry_id}")
        if target.status != "active":
            raise ValueError("only active memory can be retired")
        _require_aware(target.created_at, "memory entry timestamp")
        if corrected_at < target.created_at:
            raise ValueError("corrected_at cannot precede memory entry creation")
        found = False
        updated_entries: list[MemoryEntry] = []
        for entry in memory.entries:
            if entry.entry_id == entry_id:
                entry = replace(entry, status="retired", retired_by=actor_id,
                                retired_at=corrected_at, retirement_reason=reason)
                found = True
            updated_entries.append(entry)
        updated = ResidentMemory(resident_id, memory.version + 1, tuple(updated_entries))
        self._memories[resident_id] = updated
        return updated
