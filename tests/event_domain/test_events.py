import unittest

from backend.app.domain.events import EventStatus, ResolutionOutcome, EventStore


class EventFlowTests(unittest.TestCase):
    def test_event_can_move_through_the_caregiver_flow(self) -> None:
        store = EventStore()
        event = store.create_event(
            event_id="evt_001",
            resident_id="resident_demo_a",
            room_id="room_214",
            headline="Unusual movement detected",
        )

        self.assertEqual(event.status, EventStatus.DETECTED)
        store.open_event(event.event_id)
        store.acknowledge(event.event_id)
        store.check(event.event_id)
        resolved = store.resolve(event.event_id, ResolutionOutcome.CONFIRMED)

        self.assertEqual(resolved.status, EventStatus.RESOLVED)
        self.assertEqual(resolved.resolution_outcome, ResolutionOutcome.CONFIRMED)

    def test_invalid_status_jump_is_rejected(self) -> None:
        store = EventStore()
        event = store.create_event(
            event_id="evt_002",
            resident_id="resident_demo_a",
            room_id="room_214",
            headline="Unusual movement detected",
        )

        with self.assertRaises(ValueError):
            store.resolve(event.event_id, ResolutionOutcome.FALSE_POSITIVE)


if __name__ == "__main__":
    unittest.main()
