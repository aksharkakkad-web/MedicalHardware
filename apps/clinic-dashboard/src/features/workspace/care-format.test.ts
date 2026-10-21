import { describe, expect, it } from "vitest";
import type {
  MonitoringEventDetail,
  ResidentOverviewItem,
} from "@/lib/monitoring";
import type {
  ResidentMeasurement,
  ResidentProfile,
} from "@/lib/workspace/types";
import { concernQueue, readingIsAvailable, careTime } from "./care-format";

const resident = {
  assignmentStatus: "active",
  monitoring: { state: "active" },
} as ResidentOverviewItem;
const measurement: ResidentMeasurement = {
  residentId: "r1",
  kind: "pulse",
  label: "Pulse estimate",
  value: 72,
  unit: "bpm",
  observedAt: "2026-10-21T14:00:00Z",
  quality: "demo",
  attribution: "eligible",
  reason: "Synthetic observation",
  synthetic: true,
};

describe("care presentation safeguards", () => {
  it("keeps urgent authorized concerns in view when staff select another area", () => {
    const events = [
      {
        eventId: "watch",
        resident: { residentId: "r1" },
        priority: "watch",
        status: "open",
        createdAt: "2026-10-21T10:00:00Z",
      },
      {
        eventId: "urgent",
        resident: { residentId: "r1" },
        priority: "critical",
        status: "open",
        createdAt: "2026-10-21T11:00:00Z",
      },
      {
        eventId: "closed",
        resident: { residentId: "r1" },
        priority: "high",
        status: "resolved",
        createdAt: "2026-10-21T09:00:00Z",
      },
    ] as MonitoringEventDetail[];
    const profiles = [
      { residentId: "r1", areaId: "north" },
    ] as ResidentProfile[];
    expect(
      concernQueue(events, profiles, "south").map((event) => event.eventId),
    ).toEqual(["urgent"]);
  });

  it("does not render resident readings for paused, unavailable or conflicting assignments", () => {
    expect(readingIsAvailable(measurement, resident)).toBe(true);
    expect(
      readingIsAvailable(measurement, {
        ...resident,
        monitoring: { ...resident.monitoring, state: "paused" },
      }),
    ).toBe(false);
    expect(
      readingIsAvailable(measurement, {
        ...resident,
        assignmentStatus: "conflicting",
      }),
    ).toBe(false);
    expect(
      readingIsAvailable(
        { ...measurement, attribution: "unavailable" },
        resident,
      ),
    ).toBe(false);
    expect(readingIsAvailable({ ...measurement, value: null }, resident)).toBe(
      false,
    );
  });

  it("uses the facility timezone and leaves missing observation times unavailable", () => {
    expect(careTime(null, "America/Chicago")).toBe("Time unavailable");
    expect(careTime("2026-10-21T14:00:00Z", "America/Chicago")).toContain(
      "9:00 AM",
    );
  });
});
