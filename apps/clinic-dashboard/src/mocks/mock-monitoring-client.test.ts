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
    expect(acknowledged.overdue).toBe(false);
    expect(checked.status).toBe("checked");
    expect(resolved.status).toBe("resolved");
    expect(resolved.feedback).toMatchObject({
      actualEventLabel: "Assisted movement",
      routine: true,
    });
    expect(resolved.actionHistory.map((item) => item.action)).toEqual([
      "opened",
      "acknowledged",
      "checked",
      "resolved",
    ]);
    expect((await client.getEvent(opened.eventId)).status).toBe("resolved");
  });

  it("rejects actions that do not match the current event state", async () => {
    const client = new MockMonitoringClient();

    await expect(
      client.performEventAction("evt_unusual_movement_102", "check"),
    ).rejects.toThrow(/not available/i);
  });

  it("does not reset progress after an unknown event is requested", async () => {
    const client = new MockMonitoringClient();
    await client.performEventAction("evt_unusual_movement_102", "acknowledge");

    await expect(client.getEvent("evt_missing")).rejects.toThrow(
      /could not be found/i,
    );
    expect((await client.getEvent("evt_unusual_movement_102")).status).toBe(
      "acknowledged",
    );
  });

  it("provides contract-valid scenarios for uncertain and unavailable data", async () => {
    const client = new MockMonitoringClient();
    const unknownPattern = await client.getEvent("evt_unknown_pattern_104");
    const deviceIssue = await client.getEvent("evt_device_issue_105");
    const overdueEvent = await client.getEvent("evt_unusual_movement_102");

    expect(unknownPattern).toMatchObject({
      objectiveFamily: "Unknown anomaly",
      confidence: { dataQuality: "limited" },
      interpretation: { status: "unavailable" },
    });
    expect(deviceIssue).toMatchObject({
      confidence: { dataQuality: "unavailable" },
      interpretation: { status: "pending" },
      device: { status: "offline" },
    });
    expect(overdueEvent.overdue).toBe(true);
    expect(overdueEvent.relatedEventIds).toEqual(["evt_previous_movement_102"]);
  });

  it("keeps event progress after the client is recreated", async () => {
    const savedValues = new Map<string, string>();
    const storage = {
      getItem: (key: string) => savedValues.get(key) ?? null,
      setItem: (key: string, value: string) => savedValues.set(key, value),
    };
    const firstClient = new MockMonitoringClient(undefined, storage);

    await firstClient.performEventAction(
      "evt_unusual_movement_102",
      "acknowledge",
    );

    const recreatedClient = new MockMonitoringClient(undefined, storage);
    expect(
      (await recreatedClient.getEvent("evt_unusual_movement_102")).status,
    ).toBe("acknowledged");
  });

  it("falls back to safe fixtures when saved demo data is broken", async () => {
    const client = new MockMonitoringClient(undefined, {
      getItem: () => '[{"eventId":"evt_unusual_movement_102"}]',
      setItem: () => undefined,
    });

    expect((await client.getEvent("evt_unusual_movement_102")).status).toBe(
      "open",
    );
  });

  it("updates the resident dashboard as staff complete the event workflow", async () => {
    const client = new MockMonitoringClient();
    const eventId = "evt_unusual_movement_102";

    await client.performEventAction(eventId, "acknowledge");
    expect(
      (await client.listResidentOverview()).items[1].attention.headline,
    ).toMatch(/resident check needed/i);

    await client.performEventAction(eventId, "check");
    expect(
      (await client.listResidentOverview()).items[1].attention.headline,
    ).toMatch(/resolution feedback needed/i);

    await client.resolveEventWithFeedback(eventId, {
      outcome: "confirmed",
      actualEventLabel: "Assisted movement",
      routine: true,
    });
    const resolvedResident = (await client.listResidentOverview()).items[1];
    expect(resolvedResident.attention).toMatchObject({
      priority: "none",
      openEventCount: 0,
    });
  });
});
