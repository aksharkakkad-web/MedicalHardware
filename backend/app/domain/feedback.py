"""Trusted operator feedback and versioned resident context for toy scenarios."""

from dataclasses import dataclass, replace
from datetime import datetime
import re
from uuid import uuid4

from backend.app.domain._validation import (
    require_aware_datetime,
    require_nonblank_text,
    require_strict_bool,
)
from backend.app.domain.events import EventStatus, MonitoringEvent, ResolutionOutcome


def _normalize_event_label(value: object) -> str:
    value = require_nonblank_text(value, "actual_event_label")
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not normalized:
        raise ValueError("actual_event_label must contain letters or numbers")
    return normalized


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
    schema_version: str = "1.0"


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
    schema_version: str = "1.0"


@dataclass(frozen=True)
class ResidentMemory:
    resident_id: str
    version: int
    entries: tuple[MemoryEntry, ...]
    schema_version: str = "1.0"

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
    schema_version: str = "1.0"


class FeedbackService:
    def __init__(self) -> None:
        self._memories: dict[str, ResidentMemory] = {}
        self._feedback: dict[str, FeedbackRecord] = {}
        self._decisions_by_event_id: dict[str, LearningDecision] = {}

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
        actor_id = require_nonblank_text(actor_id, "actor_id")
        actual_event_label = _normalize_event_label(actual_event_label)
        routine = require_strict_bool(routine, "routine")
        created_at = require_aware_datetime(created_at, "created_at")
        event_timestamp = require_aware_datetime(
            event.latest_recorded_at,
            "event timestamp",
        )
        if created_at < event_timestamp:
            raise ValueError("created_at cannot precede the event timestamp")

        existing = self._decisions_by_event_id.get(event.event_id)
        if existing is not None:
            same_submission = (
                existing.feedback.resident_id == event.resident_id
                and existing.feedback.actor_id == actor_id
                and existing.feedback.outcome == event.resolution_outcome
                and existing.feedback.actual_event_label == actual_event_label
                and existing.feedback.routine == routine
            )
            if same_submission:
                return existing
            raise ValueError(
                "feedback already exists for this event; use explicit correction"
            )

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
        memory_updated = routine and actual_event_label != "unknown"
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

        baseline_window_eligible = (
            event.resolution_outcome == ResolutionOutcome.FALSE_POSITIVE
            and memory_updated
        )
        decision = LearningDecision(
            feedback,
            memory,
            memory_updated,
            baseline_window_eligible,
            True,
        )
        self._decisions_by_event_id[event.event_id] = decision
        return decision

    def correct_memory(
        self,
        *,
        resident_id: str,
        entry_id: str,
        actor_id: str,
        reason: str,
        corrected_at: datetime,
    ) -> ResidentMemory:
        actor_id = require_nonblank_text(actor_id, "actor_id")
        reason = require_nonblank_text(reason, "reason")
        corrected_at = require_aware_datetime(corrected_at, "corrected_at")
        memory = self._memories[resident_id]
        target = next((entry for entry in memory.entries if entry.entry_id == entry_id), None)
        if target is None:
            raise KeyError(f"Unknown memory entry: {entry_id}")
        if target.status != "active":
            raise ValueError("only active memory can be retired")
        target_created_at = require_aware_datetime(
            target.created_at,
            "memory entry timestamp",
        )
        if corrected_at < target_created_at:
            raise ValueError("corrected_at cannot precede memory entry creation")
        updated_entries: list[MemoryEntry] = []
        for entry in memory.entries:
            if entry.entry_id == entry_id:
                entry = replace(
                    entry,
                    status="retired",
                    retired_by=actor_id,
                    retired_at=corrected_at,
                    retirement_reason=reason,
                )
            updated_entries.append(entry)
        updated = ResidentMemory(resident_id, memory.version + 1, tuple(updated_entries))
        self._memories[resident_id] = updated
        return updated
