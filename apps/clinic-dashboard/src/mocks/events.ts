import type { MonitoringEventDetail } from "@/lib/monitoring";

function timestampBefore(now: Date, offsetMs: number): string {
  return new Date(now.getTime() - offsetMs).toISOString();
}

function openedHistory(occurredAt: string): MonitoringEventDetail["actionHistory"] {
  return [{ action: "opened", actorLabel: "Monitoring system", occurredAt, status: "open", resolutionOutcome: null }];
}

function createUnusualMovementEvent(now: Date): MonitoringEventDetail {
  const createdAt = timestampBefore(now, 48 * 60_000);
  return {
    schemaVersion: "1.0",
    eventId: "evt_unusual_movement_102",
    resident: { residentId: "res_2c8d4f", displayLabel: "Resident B", roomId: "room_6a91c3", roomLabel: "Room 102" },
    createdAt,
    lastSignalAt: timestampBefore(now, 47 * 60_000),
    status: "open",
    priority: "high",
    headline: "Unusual activity needs staff review",
    objectiveFamily: "Unusual movement",
    confidence: {
      value: 0.84,
      label: "High confidence",
      dataQuality: "good",
      limitation: "The system detected an unusual pattern, but sensor data cannot confirm what caused it.",
    },
    evidence: [
      { evidenceId: "movement_deviation", label: "Movement changed", observation: "Movement was much higher than this resident's usual pattern.", recordedAt: createdAt, quality: "good" },
      { evidenceId: "position_change", label: "Position changed", observation: "The room sensors recorded a quick downward position change.", recordedAt: timestampBefore(now, 47.5 * 60_000), quality: "good" },
      { evidenceId: "post_event_inactivity", label: "Low movement afterward", observation: "Movement stayed unusually low for the next minute.", recordedAt: timestampBefore(now, 47 * 60_000), quality: "good" },
    ],
    interpretation: {
      status: "complete",
      summary: "A large movement was followed by a quick position change and very little movement afterward.",
      uncertainty: "This is a possible explanation, not a diagnosis. A staff member must check what happened.",
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
    relatedEventIds: ["evt_previous_movement_102"],
    recurrenceCount: 2,
    overdue: true,
    overdueAt: timestampBefore(now, 18 * 60_000),
    actionHistory: openedHistory(createdAt),
    resolutionOutcome: null,
    feedback: null,
  };
}

function createPreviousMovementEvent(now: Date): MonitoringEventDetail {
  const createdAt = timestampBefore(now, 3 * 24 * 60 * 60_000);
  const resolvedAt = timestampBefore(now, 3 * 24 * 60 * 60_000 - 22 * 60_000);
  return {
    ...createUnusualMovementEvent(now),
    eventId: "evt_previous_movement_102",
    createdAt,
    lastSignalAt: timestampBefore(now, 3 * 24 * 60 * 60_000 - 60_000),
    status: "resolved",
    priority: "watch",
    headline: "Previous unusual movement review",
    relatedEventIds: ["evt_unusual_movement_102"],
    recurrenceCount: 1,
    overdue: false,
    overdueAt: null,
    actionHistory: [
      ...openedHistory(createdAt),
      { action: "acknowledged", actorLabel: "Demo caregiver", occurredAt: timestampBefore(now, 3 * 24 * 60 * 60_000 - 8 * 60_000), status: "acknowledged", resolutionOutcome: null },
      { action: "checked", actorLabel: "Demo caregiver", occurredAt: timestampBefore(now, 3 * 24 * 60 * 60_000 - 15 * 60_000), status: "checked", resolutionOutcome: null },
      { action: "resolved", actorLabel: "Demo caregiver", occurredAt: resolvedAt, status: "resolved", resolutionOutcome: "uncertain" },
    ],
    resolutionOutcome: "uncertain",
    feedback: { actualEventLabel: "Cause could not be confirmed", routine: false, createdAt: resolvedAt, submittedBy: "Demo caregiver" },
  };
}

function createUnknownPatternEvent(now: Date): MonitoringEventDetail {
  const createdAt = timestampBefore(now, 11 * 60_000);
  return {
    schemaVersion: "1.0",
    eventId: "evt_unknown_pattern_104",
    resident: { residentId: "res_4ab783", displayLabel: "Resident D", roomId: "room_85cd20", roomLabel: "Room 104" },
    createdAt,
    lastSignalAt: timestampBefore(now, 9 * 60_000),
    status: "open",
    priority: "watch",
    headline: "Unclassified pattern needs room check",
    objectiveFamily: "Unknown anomaly",
    confidence: {
      value: 0.38,
      label: "Low confidence",
      dataQuality: "limited",
      limitation: "Another person may be in the room, so the system cannot safely attribute this pattern to the resident.",
    },
    evidence: [{ evidenceId: "occupancy_ambiguity", label: "Room occupancy is unclear", observation: "The sensors may be seeing movement from more than one person.", recordedAt: createdAt, quality: "limited" }],
    interpretation: {
      status: "unavailable",
      summary: null,
      uncertainty: "An explanation was not created because the resident-specific evidence is unreliable.",
    },
    device: {
      status: "degraded",
      label: "Room data is limited",
      sources: [
        { label: "Radar", status: "limited" },
        { label: "Thermal", status: "available" },
        { label: "Wi-Fi sensing", status: "limited" },
      ],
    },
    relatedEventIds: [],
    recurrenceCount: 1,
    overdue: false,
    overdueAt: null,
    actionHistory: openedHistory(createdAt),
    resolutionOutcome: null,
    feedback: null,
  };
}

function createDeviceIssueEvent(now: Date): MonitoringEventDetail {
  const createdAt = timestampBefore(now, 18 * 60_000);
  return {
    schemaVersion: "1.0",
    eventId: "evt_device_issue_105",
    resident: { residentId: "res_d0e519", displayLabel: "Resident E", roomId: "room_1f64b8", roomLabel: "Room 105" },
    createdAt,
    lastSignalAt: createdAt,
    status: "open",
    priority: "watch",
    headline: "Room monitoring data stopped",
    objectiveFamily: "Device issue",
    confidence: {
      value: 0,
      label: "Data unavailable",
      dataQuality: "unavailable",
      limitation: "The room device is offline. The system cannot describe the resident's current activity.",
    },
    evidence: [{ evidenceId: "telemetry_stopped", label: "Sensor updates stopped", observation: "No new room sensor package has arrived for 18 minutes.", recordedAt: createdAt, quality: "unavailable" }],
    interpretation: {
      status: "pending",
      summary: null,
      uncertainty: "The device warning stays active while the explanation is pending. Staff should check the room device.",
    },
    device: {
      status: "offline",
      label: "Room sensor offline",
      sources: [
        { label: "Radar", status: "unavailable" },
        { label: "Thermal", status: "unavailable" },
        { label: "Wi-Fi sensing", status: "unavailable" },
      ],
    },
    relatedEventIds: [],
    recurrenceCount: 1,
    overdue: false,
    overdueAt: null,
    actionHistory: openedHistory(createdAt),
    resolutionOutcome: null,
    feedback: null,
  };
}

export function createEventDetailFixtures(now: Date): MonitoringEventDetail[] {
  return [
    createUnusualMovementEvent(now),
    createPreviousMovementEvent(now),
    createUnknownPatternEvent(now),
    createDeviceIssueEvent(now),
  ];
}

export function createEventDetailFixture(now: Date): MonitoringEventDetail {
  return createUnusualMovementEvent(now);
}
