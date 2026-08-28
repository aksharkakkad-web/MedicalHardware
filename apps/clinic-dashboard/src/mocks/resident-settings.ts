import type {
  ResidentMemoryResponse,
  ResidentNotificationPreferencesResponse,
} from "@/lib/monitoring";

function before(now: Date, minutes: number): string {
  return new Date(now.getTime() - minutes * 60_000).toISOString();
}

const residentIds = [
  "res_7f3a1c",
  "res_2c8d4f",
  "res_91be60",
  "res_4ab783",
  "res_d0e519",
  "res_assignment_review",
];

export function createPreferenceFixtures(
  now: Date,
): ResidentNotificationPreferencesResponse[] {
  return residentIds.map((residentId, index) => {
    if (residentId === "res_assignment_review") {
      return {
        schemaVersion: "1.0",
        residentId,
        dataAvailability: "not_yet_available",
        version: null,
        eventDelivery: null,
        awarenessDelivery: null,
        highCriticalDashboardVisibility: "always_visible",
        changedBy: null,
        changedAt: null,
      };
    }
    return {
      schemaVersion: "1.0",
      residentId,
      dataAvailability: "available",
      version: 1,
      eventDelivery: { watch: index !== 2, high: true, critical: true },
      awarenessDelivery: {
        away: true,
        return: true,
        limited: index !== 3,
        unavailable: true,
      },
      highCriticalDashboardVisibility: "always_visible",
      changedBy: "Demo administrator",
      changedAt: before(now, 1_440 + index * 30),
    };
  });
}

export function createMemoryFixtures(now: Date): ResidentMemoryResponse[] {
  return residentIds.map((residentId) => {
    if (residentId !== "res_7f3a1c") {
      return { schemaVersion: "1.0", residentId, version: 0, entries: [] };
    }

    return {
      schemaVersion: "1.0",
      residentId,
      version: 3,
      entries: [
        {
          schemaVersion: "1.0",
          entryId: "mem_a_before_breakfast",
          description: "Assisted standing is common before breakfast.",
          sourceKind: "operator",
          sourceFeedbackId: null,
          supersedesEntryId: null,
          status: "retired",
          createdBy: "Demo caregiver",
          createdAt: before(now, 4_320),
          retiredBy: "Demo caregiver",
          retiredAt: before(now, 2_880),
          retirementReason: "The routine time was entered incorrectly.",
        },
        {
          schemaVersion: "1.0",
          entryId: "mem_a_after_breakfast",
          description: "Assisted standing is common after breakfast.",
          sourceKind: "operator",
          sourceFeedbackId: null,
          supersedesEntryId: "mem_a_before_breakfast",
          status: "active",
          createdBy: "Demo caregiver",
          createdAt: before(now, 2_880),
          retiredBy: null,
          retiredAt: null,
          retirementReason: null,
        },
        {
          schemaVersion: "1.0",
          entryId: "mem_a_therapy",
          description: "Physical therapy usually happens on Tuesday afternoons.",
          sourceKind: "feedback",
          sourceFeedbackId: "fb_synthetic_therapy",
          supersedesEntryId: null,
          status: "active",
          createdBy: "Demo caregiver",
          createdAt: before(now, 1_440),
          retiredBy: null,
          retiredAt: null,
          retirementReason: null,
        },
      ],
    };
  });
}
