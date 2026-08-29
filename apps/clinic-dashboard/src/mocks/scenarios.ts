import type {
  DemoScenarioDefinition,
  DemoScenarioId,
} from "@/lib/demo-scenarios";
import type { MonitoringEventDetail } from "@/lib/monitoring";

export const SCENARIO_RESIDENT_ID = "res_7f3a1c";

export const scenarioEventIds: Partial<Record<DemoScenarioId, string>> = {
  possible_multi_person: "evt_demo_multi_person_101",
  physiological_deviation: "evt_demo_physiological_101",
};

export const demoScenarioDefinitions: DemoScenarioDefinition[] = [
  {
    scenarioId: "resident_away",
    label: "Resident leaves the room",
    summary: "Pause resident-specific monitoring without creating a warning event.",
    safetyRule: "Existing calibration history stays saved while new learning pauses.",
    expectedOutcomes: [
      "Resident A shows monitoring paused",
      "No warning event is created",
      "New baseline learning is paused",
    ],
    tone: "neutral",
    targetKind: "resident",
  },
  {
    scenarioId: "resident_returned",
    label: "Resident returns",
    summary: "Resume resident-specific monitoring after an away period.",
    safetyRule: "Returning is an awareness update, not proof that the resident is safe.",
    expectedOutcomes: [
      "Resident A shows monitoring active",
      "Eligible baseline learning can continue",
      "No warning event is created for the return",
    ],
    tone: "healthy",
    targetKind: "resident",
  },
  {
    scenarioId: "possible_multi_person",
    label: "Possible visitor or extra person",
    summary: "Limit resident-specific monitoring when room attribution is unclear.",
    safetyRule: "The system never guesses which person produced a signal.",
    expectedOutcomes: [
      "Resident A shows monitoring limited",
      "A watch item asks staff to confirm occupancy",
      "Resident-specific interpretation is unavailable",
    ],
    tone: "attention",
    targetKind: "event",
  },
  {
    scenarioId: "physiological_deviation",
    label: "Physiological pattern changes",
    summary: "Show a combined change from a personal baseline that needs staff review.",
    safetyRule: "The synthetic pattern does not identify a diagnosis or medical cause.",
    expectedOutcomes: [
      "A high-priority event appears for Resident A",
      "Evidence describes changes from personal baseline",
      "The explanation clearly states its uncertainty",
    ],
    tone: "critical",
    targetKind: "event",
  },
];

function openedHistory(createdAt: string): MonitoringEventDetail["actionHistory"] {
  return [{ action: "opened", actorLabel: "Monitoring system", occurredAt: createdAt, status: "open", resolutionOutcome: null }];
}

export function createScenarioEventFixture(
  scenarioId: DemoScenarioId,
  now: Date,
): MonitoringEventDetail | null {
  const eventId = scenarioEventIds[scenarioId];
  if (!eventId) return null;
  const createdAt = new Date(now.getTime() - 2 * 60_000).toISOString();
  const resident = { residentId: SCENARIO_RESIDENT_ID, displayLabel: "Resident A", roomId: "room_b14e2d", roomLabel: "Room 101" };

  if (scenarioId === "possible_multi_person") {
    return {
      schemaVersion: "1.0",
      eventId,
      resident,
      createdAt,
      lastSignalAt: new Date(now.getTime() - 60_000).toISOString(),
      status: "open",
      priority: "watch",
      headline: "Confirm who is in Room 101",
      objectiveFamily: "Unknown anomaly",
      confidence: {
        value: 0.34,
        label: "Low confidence",
        dataQuality: "limited",
        limitation: "Another person may be present, so the system cannot safely attribute this pattern to Resident A.",
      },
      evidence: [{
        evidenceId: "demo_occupancy_ambiguity",
        label: "Room occupancy is unclear",
        observation: "The synthetic sensors show movement that may come from more than one person.",
        recordedAt: createdAt,
        quality: "limited",
      }],
      interpretation: {
        status: "unavailable",
        summary: null,
        uncertainty: "No resident-specific explanation was created because attribution is unreliable.",
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

  return {
    schemaVersion: "1.0",
    eventId,
    resident,
    createdAt,
    lastSignalAt: new Date(now.getTime() - 45_000).toISOString(),
    status: "open",
    priority: "high",
    headline: "Combined pattern change needs staff review",
    objectiveFamily: "Combined physiological deviation",
    confidence: {
      value: 0.72,
      label: "Moderate confidence",
      dataQuality: "good",
      limitation: "This synthetic pattern differs from the resident's baseline, but it cannot identify a medical cause.",
    },
    evidence: [
      {
        evidenceId: "demo_respiration_change",
        label: "Breathing pattern changed",
        observation: "The synthetic breathing pattern stayed different from this resident's usual resting pattern.",
        recordedAt: createdAt,
        quality: "good",
      },
      {
        evidenceId: "demo_rest_pattern_change",
        label: "Rest pattern changed",
        observation: "Movement and position signals also differed from the resident's personal baseline.",
        recordedAt: new Date(now.getTime() - 75_000).toISOString(),
        quality: "good",
      },
    ],
    interpretation: {
      status: "complete",
      summary: "Several synthetic signals changed together compared with Resident A's personal baseline.",
      uncertainty: "This is not a diagnosis. The sensors cannot determine a medical cause, so staff must check the resident.",
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
    overdue: false,
    overdueAt: null,
    actionHistory: openedHistory(createdAt),
    resolutionOutcome: null,
    feedback: null,
  };
}
