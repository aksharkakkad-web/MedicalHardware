import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from backend.app.domain.events import (
    EventPriority,
    EventStatus,
    EventStore,
    ResolutionOutcome,
    SyntheticEventEpisodePolicy,
)
from backend.app.domain.feedback import MemoryEntry, ResidentMemory
from backend.app.domain.monitoring import PresenceState, derive_monitoring_snapshot


class EventFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = EventStore(quiet_gap=timedelta(minutes=5))
        self.started = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)

    def record(self, *, at: datetime, priority: EventPriority = EventPriority.HIGH):
        return self.store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=priority,
            observed_at=at,
        )

    def test_related_signals_inside_gap_update_one_episode(self) -> None:
        first = self.record(at=self.started)
        updated = self.record(at=self.started + timedelta(minutes=2))

        self.assertEqual(updated.event_id, first.event_id)
        self.assertEqual(updated.signal_count, 2)

    def test_related_signals_at_quiet_gap_boundary_update_one_episode(self) -> None:
        first = self.record(at=self.started)
        boundary = self.record(at=self.started + timedelta(minutes=5))
        after_gap = self.record(
            at=self.started + timedelta(minutes=10, microseconds=1)
        )

        self.assertEqual(boundary.event_id, first.event_id)
        self.assertEqual(boundary.signal_count, 2)
        self.assertNotEqual(after_gap.event_id, first.event_id)

    def test_open_signal_after_gap_creates_linked_event(self) -> None:
        first = self.record(at=self.started)
        recurrence = self.record(at=self.started + timedelta(minutes=6))

        self.assertNotEqual(recurrence.event_id, first.event_id)
        self.assertEqual(recurrence.related_event_ids, (first.event_id,))
        self.assertEqual(recurrence.recurrence_count, 2)
        self.assertEqual(recurrence.status, EventStatus.OPEN)

    def test_out_of_order_signal_is_rejected(self) -> None:
        first = self.record(at=self.started + timedelta(minutes=10))

        with self.assertRaises(ValueError):
            self.record(at=self.started)

        stored = self.store.get(first.event_id)
        self.assertEqual(stored.created_at, self.started + timedelta(minutes=10))
        self.assertEqual(stored.last_signal_at, self.started + timedelta(minutes=10))

    def test_grouped_signal_cannot_precede_latest_caregiver_action(self) -> None:
        event = self.record(at=self.started)
        acknowledged = self.store.acknowledge(
            event.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=4),
        )

        with self.assertRaises(ValueError):
            self.record(at=self.started + timedelta(minutes=2))

        self.assertEqual(self.store.get(event.event_id), acknowledged)

    def test_recurrence_cannot_precede_predecessor_resolution(self) -> None:
        event = self.record(at=self.started)
        self.store.acknowledge(
            event.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=1),
        )
        self.store.check(
            event.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=2),
        )
        resolved = self.store.resolve(
            event.event_id,
            ResolutionOutcome.FALSE_POSITIVE,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=3),
        )

        with self.assertRaises(ValueError):
            self.record(at=self.started + timedelta(minutes=2, seconds=30))

        self.assertEqual(self.store.get(event.event_id), resolved)

    def test_signal_cannot_precede_history_on_an_older_related_episode(self) -> None:
        first = self.record(at=self.started)
        second = self.record(at=self.started + timedelta(minutes=6))
        acknowledged_first = self.store.acknowledge(
            first.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=10),
        )

        with self.assertRaises(ValueError):
            self.record(at=self.started + timedelta(minutes=7))

        self.assertEqual(self.store.get(first.event_id), acknowledged_first)
        self.assertEqual(self.store.get(second.event_id), second)

    def test_recurrence_after_resolution_creates_linked_event(self) -> None:
        first = self.record(at=self.started)
        self.store.acknowledge(
            first.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=1),
        )
        self.store.check(
            first.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=2),
        )
        resolved = self.store.resolve(
            first.event_id,
            ResolutionOutcome.FALSE_POSITIVE,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=3),
        )

        recurrence = self.record(at=self.started + timedelta(minutes=10))

        self.assertNotEqual(recurrence.event_id, first.event_id)
        self.assertEqual(recurrence.related_event_ids, (first.event_id,))
        self.assertEqual(recurrence.recurrence_count, 2)
        self.assertEqual(resolved.status, EventStatus.RESOLVED)

    def test_high_and_critical_events_become_overdue_instead_of_expiring(self) -> None:
        for offset, priority in enumerate((EventPriority.HIGH, EventPriority.CRITICAL)):
            with self.subTest(priority=priority):
                event = self.record(
                    at=self.started + timedelta(minutes=offset * 10),
                    priority=priority,
                )
                overdue = self.store.mark_overdue(
                    event.event_id,
                    at=event.created_at + timedelta(minutes=6),
                )

                self.assertTrue(overdue.overdue)
                self.assertEqual(
                    overdue.overdue_at,
                    event.created_at + timedelta(minutes=6),
                )
                self.assertEqual(overdue.status, EventStatus.OPEN)

    def test_watch_event_never_receives_overdue_escalation(self) -> None:
        event = self.record(at=self.started, priority=EventPriority.WATCH)

        with self.assertRaises(ValueError):
            self.store.mark_overdue(
                event.event_id,
                at=self.started + timedelta(minutes=6),
            )

    def test_invalid_status_jump_is_rejected(self) -> None:
        event = self.record(at=self.started)
        with self.assertRaises(ValueError):
            self.store.resolve(
                event.event_id,
                ResolutionOutcome.CONFIRMED,
                actor_id="operator_001",
                at=self.started + timedelta(minutes=1),
            )

    def test_resolved_event_snapshot_cannot_reopen_or_transition_again(self) -> None:
        event = self.record(at=self.started)
        self.store.acknowledge(
            event.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=1),
        )
        self.store.check(
            event.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=2),
        )
        resolved = self.store.resolve(
            event.event_id,
            ResolutionOutcome.CONFIRMED,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=3),
        )

        with self.assertRaises(FrozenInstanceError):
            resolved.status = EventStatus.OPEN
        with self.assertRaises(ValueError):
            self.store.acknowledge(
                resolved.event_id,
                actor_id="operator_001",
                at=self.started + timedelta(minutes=4),
            )

        self.assertEqual(self.store.get(resolved.event_id).status, EventStatus.RESOLVED)

    def test_all_resolution_outcomes_are_preserved(self) -> None:
        for offset, outcome in enumerate(ResolutionOutcome):
            with self.subTest(outcome=outcome):
                event = self.record(at=self.started + timedelta(minutes=offset * 10))
                self.store.acknowledge(
                    event.event_id,
                    actor_id="operator_001",
                    at=event.created_at + timedelta(minutes=1),
                )
                self.store.check(
                    event.event_id,
                    actor_id="operator_001",
                    at=event.created_at + timedelta(minutes=2),
                )

                resolved = self.store.resolve(
                    event.event_id,
                    outcome,
                    actor_id="operator_001",
                    at=event.created_at + timedelta(minutes=3),
                )

                self.assertEqual(resolved.resolution_outcome, outcome)

    def test_invalid_resolution_outcome_is_rejected(self) -> None:
        event = self.record(at=self.started)
        self.store.acknowledge(
            event.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=1),
        )
        self.store.check(
            event.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=2),
        )

        with self.assertRaises(ValueError):
            self.store.resolve(
                event.event_id,
                "other",
                actor_id="operator_001",
                at=self.started + timedelta(minutes=3),
            )

    def test_human_lifecycle_actions_have_immutable_actor_and_time_history(self) -> None:
        opened = self.record(at=self.started)
        acknowledged = self.store.acknowledge(
            opened.event_id,
            actor_id="operator_001",
            at=self.started + timedelta(minutes=1),
        )
        checked = self.store.check(
            opened.event_id,
            actor_id="operator_002",
            at=self.started + timedelta(minutes=2),
        )
        resolved = self.store.resolve(
            opened.event_id,
            ResolutionOutcome.FALSE_POSITIVE,
            actor_id="operator_003",
            at=self.started + timedelta(minutes=3),
        )

        self.assertEqual(
            tuple(entry.action for entry in resolved.action_history),
            ("opened", "acknowledged", "checked", "resolved"),
        )
        self.assertEqual(
            tuple(entry.actor_id for entry in resolved.action_history),
            (
                "system:monitoring_event",
                "operator_001",
                "operator_002",
                "operator_003",
            ),
        )
        self.assertEqual(
            tuple(entry.occurred_at for entry in resolved.action_history),
            tuple(
                self.started + timedelta(minutes=offset)
                for offset in range(4)
            ),
        )
        self.assertEqual(len(opened.action_history), 1)
        self.assertEqual(len(acknowledged.action_history), 2)
        self.assertEqual(len(checked.action_history), 3)
        with self.assertRaises(FrozenInstanceError):
            resolved.action_history[-1].actor_id = "operator_other"

    def test_priority_escalation_preserves_attributable_history(self) -> None:
        opened = self.record(at=self.started, priority=EventPriority.WATCH)
        escalated = self.store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=EventPriority.HIGH,
            observed_at=self.started + timedelta(minutes=2),
            actor_id="system:warning_policy",
        )

        self.assertEqual(opened.priority, EventPriority.WATCH)
        self.assertEqual(escalated.priority, EventPriority.HIGH)
        self.assertEqual(len(opened.priority_history), 1)
        self.assertEqual(len(escalated.priority_history), 2)
        change = escalated.priority_history[-1]
        self.assertEqual(change.previous_priority, EventPriority.WATCH)
        self.assertEqual(change.priority, EventPriority.HIGH)
        self.assertEqual(change.actor_id, "system:warning_policy")
        self.assertEqual(
            change.changed_at,
            self.started + timedelta(minutes=2),
        )
        with self.assertRaises(FrozenInstanceError):
            change.priority = EventPriority.CRITICAL

    def test_human_lifecycle_rejects_unattributable_or_unordered_actions(self) -> None:
        event = self.record(at=self.started)
        invalid_actions = (
            {
                "actor_id": "",
                "at": self.started + timedelta(minutes=1),
            },
            {
                "actor_id": "operator_001",
                "at": datetime(2026, 8, 26, 12, 1),
            },
            {
                "actor_id": "operator_001",
                "at": "2026-08-26T12:01:00Z",
            },
            {
                "actor_id": "operator_001",
                "at": self.started - timedelta(seconds=1),
            },
        )

        for values in invalid_actions:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.store.acknowledge(event.event_id, **values)

        self.assertEqual(self.store.get(event.event_id), event)

    def test_record_signal_rejects_malformed_ids_enums_and_timestamps(self) -> None:
        valid = {
            "resident_id": "resident_demo_a",
            "room_id": "room_214",
            "objective_family": "unusual_movement",
            "headline": "Unusual movement detected",
            "priority": EventPriority.HIGH,
            "observed_at": self.started,
        }
        invalid_overrides = (
            {"resident_id": ""},
            {"room_id": "   "},
            {"objective_family": None},
            {"headline": ""},
            {"priority": "urgent"},
            {"observed_at": datetime(2026, 8, 26, 12, 0)},
            {"observed_at": "2026-08-26T12:00:00Z"},
        )

        for override in invalid_overrides:
            values = valid | override
            with self.subTest(override=override), self.assertRaises(ValueError):
                EventStore().record_signal(**values)

    def test_valid_string_enums_are_normalized_at_event_boundaries(self) -> None:
        event = EventStore().record_signal(
            resident_id=" resident_demo_a ",
            room_id=" room_214 ",
            objective_family=" unusual_movement ",
            headline=" Unusual movement detected ",
            priority="high",
            observed_at=self.started,
        )

        self.assertEqual(event.resident_id, "resident_demo_a")
        self.assertEqual(event.room_id, "room_214")
        self.assertEqual(event.objective_family, "unusual_movement")
        self.assertEqual(event.headline, "Unusual movement detected")
        self.assertIs(event.priority, EventPriority.HIGH)

    def test_event_lookup_and_overdue_boundary_reject_malformed_values(self) -> None:
        with self.assertRaises(ValueError):
            self.store.get(" ")

        event = self.record(at=self.started)
        for invalid_time in (
            datetime(2026, 8, 26, 12, 6),
            "2026-08-26T12:06:00Z",
        ):
            with self.subTest(invalid_time=invalid_time), self.assertRaises(ValueError):
                self.store.mark_overdue(event.event_id, at=invalid_time)

        self.assertIsNone(self.store.get(event.event_id).overdue_at)

    def test_overdue_timestamp_cannot_precede_latest_episode_history(self) -> None:
        event = self.record(at=self.started)
        updated = self.record(at=self.started + timedelta(minutes=4))

        with self.assertRaises(ValueError):
            self.store.mark_overdue(
                updated.event_id,
                at=self.started + timedelta(minutes=3),
            )

        self.assertEqual(self.store.get(event.event_id), updated)
        self.assertIsNone(self.store.get(event.event_id).overdue_at)

    def test_quiet_gap_behavior_carries_synthetic_versioned_policy(self) -> None:
        policy = SyntheticEventEpisodePolicy(
            quiet_gap=timedelta(minutes=2),
            policy_version="synthetic_episode_policy_test_v7",
        )
        store = EventStore(policy=policy)
        first = store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=EventPriority.HIGH,
            observed_at=self.started,
        )
        recurrence = store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=EventPriority.HIGH,
            observed_at=self.started + timedelta(minutes=2, microseconds=1),
        )

        self.assertTrue(store.policy.test_only)
        self.assertTrue(first.episode_policy_test_only)
        self.assertEqual(first.episode_policy_version, policy.policy_version)
        self.assertNotEqual(recurrence.event_id, first.event_id)

    def test_synthetic_episode_policy_rejects_malformed_values(self) -> None:
        invalid_values = (
            {"quiet_gap": timedelta(0), "policy_version": "policy_v1"},
            {"quiet_gap": "five minutes", "policy_version": "policy_v1"},
            {"quiet_gap": timedelta(minutes=5), "policy_version": " "},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(ValueError):
                SyntheticEventEpisodePolicy(**values)

    def test_supplied_monitoring_snapshot_gates_resident_event_creation(self) -> None:
        away = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_AWAY,
            signal_quality=0.9,
        )
        visitor = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.POSSIBLE_MULTI_PERSON,
            signal_quality=0.9,
        )
        resumed = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_PRESENT,
            signal_quality=0.9,
        )

        for snapshot in (away, visitor):
            with self.subTest(snapshot=snapshot), self.assertRaises(ValueError):
                self.store.record_signal(
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    objective_family="unusual_movement",
                    headline="Unusual movement detected",
                    priority=EventPriority.HIGH,
                    observed_at=self.started,
                    monitoring_snapshot=snapshot,
                )

        event = self.store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=EventPriority.HIGH,
            observed_at=self.started,
            monitoring_snapshot=resumed,
        )
        self.assertEqual(event.recurrence_count, 1)

    def test_event_records_resident_memory_references_without_changing_priority(self) -> None:
        entry = MemoryEntry(
            entry_id="memory_001",
            description="assisted_transfer",
            source_feedback_id="feedback_001",
            status="active",
            created_by="operator_001",
            created_at=self.started,
        )
        memory = ResidentMemory(
            resident_id="resident_demo_a",
            version=3,
            entries=(entry,),
        )

        event = self.store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=EventPriority.HIGH,
            observed_at=self.started + timedelta(minutes=1),
            resident_memory=memory,
        )

        self.assertEqual(event.priority, EventPriority.HIGH)
        self.assertEqual(event.resident_memory_version, 3)
        self.assertEqual(event.resident_memory_entry_ids, ("memory_001",))

        mismatched = ResidentMemory(
            resident_id="resident_other",
            version=1,
            entries=(),
        )
        with self.assertRaises(ValueError):
            EventStore().record_signal(
                resident_id="resident_demo_a",
                room_id="room_214",
                objective_family="unusual_movement",
                headline="Unusual movement detected",
                priority=EventPriority.HIGH,
                observed_at=self.started,
                resident_memory=mismatched,
            )


if __name__ == "__main__":
    unittest.main()
