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

  it("returns a contract-shaped event and preserves action progress", async () => {
    const client = new MockMonitoringClient(
      () => new Date("2026-08-27T18:00:00.000Z"),
    );

    const opened = await client.getEvent("evt_unusual_movement_102");
    const acknowledged = await client.performEventAction(
      opened.eventId,
      "acknowledge",
    );
    const checked = await client.performEventAction(opened.eventId, "check");
    const resolved = await client.resolveEventWithFeedback(opened.eventId, {
      outcome: "confirmed",
      actualEventLabel: "Assisted movement",
      routine: true,
    });

    expect(opened.status).toBe("open");
    expect(opened.evidence).toHaveLength(3);
    expect(acknowledged.status).toBe("acknowledged");
    expect(checked.status).toBe("checked");
    expect(resolved.status).toBe("resolved");
    expect(resolved.feedback).toMatchObject({
      actualEventLabel: "Assisted movement",
      routine: true,
    });
    expect((await client.getEvent(opened.eventId)).status).toBe("resolved");
  });

  it("rejects actions that do not match the current event state", async () => {
    const client = new MockMonitoringClient();

    await expect(
      client.performEventAction("evt_unusual_movement_102", "check"),
    ).rejects.toThrow(/not available/i);
  });
});
