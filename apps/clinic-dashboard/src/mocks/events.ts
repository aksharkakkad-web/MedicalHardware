import type { MonitoringEventDetail } from "@/lib/monitoring";

function timestampBefore(now: Date, offsetMs: number): string {
  return new Date(now.getTime() - offsetMs).toISOString();
}

export function createEventDetailFixture(now: Date): MonitoringEventDetail {
  return {
    schemaVersion: "1.0",
    eventId: "evt_unusual_movement_102",
    resident: {
      residentId: "res_2c8d4f",
      displayLabel: "Resident B",
      roomId: "room_6a91c3",
      roomLabel: "Room 102",
    },
    createdAt: timestampBefore(now, 8 * 60_000),
    lastSignalAt: timestampBefore(now, 7 * 60_000),
    status: "open",
    priority: "high",
    headline: "Unusual activity needs staff review",
    objectiveFamily: "Unusual movement",
    confidence: {
      value: 0.84,
      label: "High confidence",
      dataQuality: "good",
      limitation:
        "The system detected an unusual pattern, but sensor data cannot confirm what caused it.",
    },
    evidence: [
      {
        evidenceId: "movement_deviation",
        label: "Movement changed",
        observation: "Movement was much higher than this resident's usual pattern.",
        recordedAt: timestampBefore(now, 8 * 60_000),
        quality: "good",
      },
      {
        evidenceId: "position_change",
        label: "Position changed",
        observation: "The room sensors recorded a quick downward position change.",
        recordedAt: timestampBefore(now, 7.5 * 60_000),
        quality: "good",
      },
      {
        evidenceId: "post_event_inactivity",
        label: "Low movement afterward",
        observation: "Movement stayed unusually low for the next minute.",
        recordedAt: timestampBefore(now, 7 * 60_000),
        quality: "good",
      },
    ],
    interpretation: {
      status: "complete",
      summary:
        "A large movement was followed by a quick position change and very little movement afterward.",
      uncertainty:
        "This is a possible explanation, not a diagnosis. A staff member must check what happened.",
    },
    device: {
      status: "online",
      label: "Room sensor online",
      sources: [
        { label: "Radar", status: "available" },
        { label: "Thermal", status: "available" },
        { label: "Wi-Fi sensing", status: "available" },
      ],
    },
    relatedEventIds: [],
    recurrenceCount: 1,
  };
}
