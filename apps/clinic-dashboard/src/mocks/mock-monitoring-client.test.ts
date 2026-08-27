import { describe, expect, it } from "vitest";
import { MockMonitoringClient } from "./mock-monitoring-client";

describe("MockMonitoringClient", () => {
  it("returns five synthetic residents covering honest monitoring states", async () => {
    const result = await new MockMonitoringClient().listResidentOverview();

    const expectedScenarios = [
      {
        monitoringState: "active",
        attentionPriority: "none",
        deviceStatus: "online",
      },
      {
        monitoringState: "active",
        attentionPriority: "high",
        deviceStatus: "online",
      },
      {
        monitoringState: "paused",
        attentionPriority: "none",
        deviceStatus: "online",
        reason: /away/i,
      },
      {
        monitoringState: "limited",
        attentionPriority: "watch",
        deviceStatus: "online",
        reason: /(multiple-person|visitor)/i,
      },
      {
        monitoringState: "unavailable",
        attentionPriority: "watch",
        deviceStatus: "offline",
      },
    ] as const;

    expect(result.schemaVersion).toBe("1.0");
    expect(result.items).toHaveLength(5);
    expectedScenarios.forEach((expected, index) => {
      const item = result.items[index];

      expect(item.monitoring.state).toBe(expected.monitoringState);
      expect(item.attention.priority).toBe(expected.attentionPriority);
      expect(item.device.status).toBe(expected.deviceStatus);
      if ("reason" in expected) {
        expect(item.monitoring.reason).toMatch(expected.reason);
      }
    });
    expect(result.items.every((item) => item.schemaVersion === "1.0")).toBe(
      true,
    );
  });

  it("uses the injected current time for fresh deterministic timestamps", async () => {
    const fixedNow = new Date("2030-04-05T12:34:56.000Z");
    const result = await new MockMonitoringClient(
      () => fixedNow,
    ).listResidentOverview();
    const expectedOffsetsMs = [15_000, 30_000, 300_000, 110_000, 1_080_000];

    expect(result.generatedAt).toBe(fixedNow.toISOString());
    expect(result.items.map((item) => item.monitoring.lastUpdatedAt)).toEqual(
      expectedOffsetsMs.map((offset) =>
        new Date(fixedNow.getTime() - offset).toISOString(),
      ),
    );
  });

  it("returns a clone that cannot mutate later responses", async () => {
    const client = new MockMonitoringClient();
    const firstResult = await client.listResidentOverview();

    firstResult.items[0].displayLabel = "Mutated label";

    const nextResult = await client.listResidentOverview();

    expect(nextResult.items[0].displayLabel).not.toBe("Mutated label");
  });
});
