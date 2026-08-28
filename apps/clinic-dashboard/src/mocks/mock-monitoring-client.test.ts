import { describe, expect, it } from "vitest";
import { MockMonitoringClient } from "./mock-monitoring-client";

describe("MockMonitoringClient", () => {
  it("returns a complete device inventory without inventing missing setup data", async () => {
    const client = new MockMonitoringClient(
      () => new Date("2026-08-27T18:00:00.000Z"),
    );
    const result = await client.listDevices();

    expect(result.schemaVersion).toBe("1.0");
    expect(result.items).toHaveLength(6);
    expect(result.items.map((item) => item.health.status)).toEqual([
      "online",
      "buffering",
      "online",
      "degraded",
      "offline",
      "unavailable",
    ]);
    expect(result.items.at(-1)).toMatchObject({
      assignmentStatus: "unassigned",
      roomId: null,
      residentId: null,
      health: { dataAvailability: "not_yet_available", lastSeenAt: null },
      setup: { version: 0, state: "not_started" },
    });
  });

  it("returns cloned device details and rejects unknown devices", async () => {
    const client = new MockMonitoringClient();
    const first = await client.getDevice("dev_room_104");

    first.device.displayLabel = "Changed outside client";

    expect((await client.getDevice("dev_room_104")).device).toMatchObject({
      displayLabel: "Northstar 104",
      health: { status: "degraded", dataAvailability: "limited" },
    });
    await expect(client.getDevice("dev_missing")).rejects.toThrow(/could not be found/i);
  });

  it("returns six synthetic residents covering honest monitoring states", async () => {
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
      {
        monitoringState: "unavailable",
        attentionPriority: "watch",
        deviceStatus: "unknown",
      },
    ] as const;

    expect(result.schemaVersion).toBe("1.0");
    expect(result.items).toHaveLength(6);
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
    const expectedOffsetsMs = [15_000, 30_000, 300_000, 110_000, 1_080_000, 300_000];

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

  it("lists event work in newest-first order and finds a resident", async () => {
    const client = new MockMonitoringClient(
      () => new Date("2026-08-27T18:00:00.000Z"),
    );

    const events = await client.listEvents();
    const resident = await client.getResident("res_2c8d4f");

    expect(events.items).toHaveLength(4);
    expect(events.items[0].eventId).toBe("evt_unknown_pattern_104");
    expect(resident.resident.displayLabel).toBe("Resident B");
    expect(resident.events.map((event) => event.eventId)).toEqual([
      "evt_unusual_movement_102",
      "evt_previous_movement_102",
    ]);
    await expect(client.getResident("res_missing")).rejects.toThrow(
      /could not be found/i,
    );
  });

  it("shows stored event progress in event and resident lists", async () => {
    const client = new MockMonitoringClient();
    await client.performEventAction("evt_unusual_movement_102", "acknowledge");

    expect(
      (await client.listEvents()).items.find(
        (event) => event.eventId === "evt_unusual_movement_102",
      )?.status,
    ).toBe("acknowledged");
    expect((await client.getResident("res_2c8d4f")).events[0].status).toBe(
      "acknowledged",
    );
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

  it("restarts only selected calibration areas and preserves the rest", async () => {
    const client = new MockMonitoringClient(() => new Date("2026-08-28T12:00:00.000Z"));

    const result = await client.recordSetupChange("res_7f3a1c", {
      reason: "device_moved",
      affectedDimensions: ["movement"],
      expectedCalibrationVersion: 1,
    });

    expect(result.setup).toMatchObject({ version: 2, status: "partial", setupVersion: "setup_room_b14e2d_v2" });
    expect(result.setup.dimensions).toMatchObject([
      { dimension: "movement", status: "calibrating", eligibleWindows: 0 },
      { dimension: "respiratory_rate", status: "established", eligibleWindows: 12 },
    ]);
    expect(result.setup.setupChanges.at(-1)).toMatchObject({ reason: "device_moved", affectedDimensions: ["movement"] });
  });

  it("saves setup changes and blocks changes when assignment conflicts", async () => {
    const savedValues = new Map<string, string>();
    const storage = {
      getItem: (key: string) => savedValues.get(key) ?? null,
      setItem: (key: string, value: string) => savedValues.set(key, value),
    };
    const firstClient = new MockMonitoringClient(undefined, storage);
    await firstClient.recordSetupChange("res_7f3a1c", { reason: "room_layout_changed", affectedDimensions: ["movement"], expectedCalibrationVersion: 1 });

    expect((await new MockMonitoringClient(undefined, storage).getResidentMonitoringSetup("res_7f3a1c")).setup.version).toBe(2);
    await expect(firstClient.recordSetupChange("res_assignment_review", { reason: "resident_moved", affectedDimensions: ["movement"], expectedCalibrationVersion: 0 })).rejects.toThrow(/resolve the room assignment/i);
  });

  it("rejects stale changes and derives the overall state from every area", async () => {
    const client = new MockMonitoringClient();

    await expect(client.recordSetupChange("res_7f3a1c", {
      reason: "device_moved",
      affectedDimensions: ["movement"],
      expectedCalibrationVersion: 0,
    })).rejects.toThrow(/changed in another session/i);

    const stillCalibrating = await client.recordSetupChange("res_2c8d4f", {
      reason: "room_layout_changed",
      affectedDimensions: ["movement"],
      expectedCalibrationVersion: 1,
    });
    expect(stillCalibrating.setup.status).toBe("calibrating");

    const fullRestart = await client.recordSetupChange("res_7f3a1c", {
      reason: "core_sensor_replaced",
      affectedDimensions: ["movement", "respiratory_rate"],
      expectedCalibrationVersion: 1,
    });
    expect(fullRestart.setup.status).toBe("calibrating");
  });

  it("keeps established calibration history when current learning is paused", async () => {
    const away = (await new MockMonitoringClient().getResidentMonitoringSetup("res_91be60")).setup;

    expect(away).toMatchObject({ status: "established", learningState: "paused" });
    expect(away.dimensions.every((dimension) => dimension.status === "established")).toBe(true);
  });

  it("saves first-time and existing notification preferences with version checks", async () => {
    const client = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"));
    const first = await client.getNotificationPreferences("res_assignment_review");
    expect(first).toMatchObject({ dataAvailability: "not_yet_available", version: null });

    const saved = await client.updateNotificationPreferences("res_assignment_review", {
      expectedVersion: 0,
      eventDelivery: { watch: false, high: true, critical: false },
      awarenessDelivery: { away: true, return: true, limited: false, unavailable: true },
    });
    expect(saved).toMatchObject({
      dataAvailability: "available",
      version: 1,
      highCriticalDashboardVisibility: "always_visible",
      eventDelivery: { critical: false },
      changedAt: "2026-08-28T18:00:00.000Z",
    });

    await expect(client.updateNotificationPreferences("res_assignment_review", {
      expectedVersion: 0,
      eventDelivery: saved.eventDelivery!,
      awarenessDelivery: saved.awarenessDelivery!,
    })).rejects.toThrow(/changed in another session/i);
  });

  it("adds, corrects, and retires resident context without deleting history", async () => {
    const client = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"));
    const added = await client.addMemoryEntry("res_2c8d4f", {
      expectedVersion: 0,
      description: "  Assisted walking is common after lunch.  ",
    });
    expect(added).toMatchObject({ version: 1, entries: [{ status: "active", sourceKind: "operator", description: "Assisted walking is common after lunch." }] });

    const originalId = added.entries[0].entryId;
    const corrected = await client.correctMemoryEntry("res_2c8d4f", originalId, {
      expectedVersion: 1,
      description: "Assisted walking is common before lunch.",
      reason: "The time was recorded incorrectly.",
    });
    expect(corrected.version).toBe(2);
    expect(corrected.entries).toHaveLength(2);
    expect(corrected.entries[0]).toMatchObject({ status: "retired", retirementReason: "The time was recorded incorrectly." });
    expect(corrected.entries[1]).toMatchObject({ status: "active", supersedesEntryId: originalId });

    const retired = await client.retireMemoryEntry("res_2c8d4f", corrected.entries[1].entryId, {
      expectedVersion: 2,
      reason: "This routine is no longer current.",
    });
    expect(retired.version).toBe(3);
    expect(retired.entries).toHaveLength(2);
    expect(retired.entries.every((entry) => entry.status === "retired")).toBe(true);
  });

  it("preserves resident settings when the mock client is recreated", async () => {
    const savedValues = new Map<string, string>();
    const storage = {
      getItem: (key: string) => savedValues.get(key) ?? null,
      setItem: (key: string, value: string) => savedValues.set(key, value),
    };
    const firstClient = new MockMonitoringClient(undefined, storage);
    await firstClient.addMemoryEntry("res_2c8d4f", { expectedVersion: 0, description: "A synthetic routine." });
    const preferences = await firstClient.getNotificationPreferences("res_7f3a1c");
    await firstClient.updateNotificationPreferences("res_7f3a1c", {
      expectedVersion: preferences.version!,
      eventDelivery: { ...preferences.eventDelivery!, watch: false },
      awarenessDelivery: preferences.awarenessDelivery!,
    });

    const recreated = new MockMonitoringClient(undefined, storage);
    expect((await recreated.getResidentMemory("res_2c8d4f")).version).toBe(1);
    expect((await recreated.getNotificationPreferences("res_7f3a1c")).eventDelivery?.watch).toBe(false);
  });

  it("turns routine event feedback into traceable resident context", async () => {
    const client = new MockMonitoringClient();
    await client.performEventAction("evt_unusual_movement_102", "acknowledge");
    await client.performEventAction("evt_unusual_movement_102", "check");
    await client.resolveEventWithFeedback("evt_unusual_movement_102", {
      outcome: "false_positive",
      actualEventLabel: "Assisted movement",
      routine: true,
    });

    const memory = await client.getResidentMemory("res_2c8d4f");
    expect(memory).toMatchObject({ version: 1 });
    expect(memory.entries[0]).toMatchObject({
      description: "Assisted movement",
      sourceKind: "feedback",
      sourceFeedbackId: "fb_evt_unusual_movement_102",
      status: "active",
    });
  });

  it("drives the resident-away and returned walkthroughs without creating warnings", async () => {
    const client = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"));

    await client.applyDemoScenario("resident_away");
    const away = await client.getResident("res_7f3a1c");
    expect(away.resident).toMatchObject({
      monitoring: { state: "paused", reason: expect.stringMatching(/away/i) },
      attention: { priority: "none", openEventCount: 0 },
    });
    expect((await client.getResidentMonitoringSetup("res_7f3a1c")).setup).toMatchObject({
      status: "established",
      learningState: "paused",
    });
    expect(away.events).toHaveLength(0);

    await client.applyDemoScenario("resident_returned");
    const returned = await client.getResident("res_7f3a1c");
    expect(returned.resident).toMatchObject({
      monitoring: { state: "active", reason: expect.stringMatching(/returned/i) },
      attention: { priority: "none", openEventCount: 0 },
    });
    expect((await client.getResidentMonitoringSetup("res_7f3a1c")).setup.learningState).toBe("active");
  });

  it("creates honest multi-person and physiological walkthrough events", async () => {
    const client = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"));

    const multiState = await client.applyDemoScenario("possible_multi_person");
    const multiResident = await client.getResident("res_7f3a1c");
    const multiEvent = multiResident.events.find((event) => event.eventId === multiState.targetEventId);
    expect(multiResident.resident).toMatchObject({
      monitoring: { state: "limited", reason: expect.stringMatching(/another person|multiple-person/i) },
      attention: { priority: "watch", openEventCount: 1 },
    });
    expect(multiEvent).toMatchObject({
      objectiveFamily: "Unknown anomaly",
      priority: "watch",
      confidence: { dataQuality: "limited", limitation: expect.stringMatching(/cannot safely attribute/i) },
    });

    const physiologicalState = await client.applyDemoScenario("physiological_deviation");
    const physiologicalEvent = (await client.listEvents()).items.find((event) => event.eventId === physiologicalState.targetEventId);
    expect(physiologicalEvent).toMatchObject({
      objectiveFamily: "Combined physiological deviation",
      priority: "high",
      confidence: { limitation: expect.stringMatching(/cannot identify a medical cause/i) },
      interpretation: { uncertainty: expect.stringMatching(/not a diagnosis/i) },
    });
  });

  it("persists, clones, validates, and resets the active demo scenario", async () => {
    const savedValues = new Map<string, string>();
    const storage = {
      getItem: (key: string) => savedValues.get(key) ?? null,
      setItem: (key: string, value: string) => savedValues.set(key, value),
    };
    const first = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"), storage);
    const applied = await first.applyDemoScenario("possible_multi_person");
    applied.activeScenarioId = null;

    const recreated = new MockMonitoringClient(undefined, storage);
    expect((await recreated.getActiveDemoScenario()).activeScenarioId).toBe("possible_multi_person");
    expect((await recreated.getResident("res_7f3a1c")).resident.monitoring.state).toBe("limited");

    await recreated.resetDemoScenario();
    expect((await recreated.getActiveDemoScenario()).activeScenarioId).toBeNull();
    expect((await recreated.getResident("res_7f3a1c")).resident.monitoring.state).toBe("active");

    savedValues.set("adaptive-care:demo-scenario:v1", JSON.stringify({ schemaVersion: "1.0", activeScenarioId: "invented", appliedAt: null }));
    expect((await new MockMonitoringClient(undefined, storage).getActiveDemoScenario()).activeScenarioId).toBeNull();
  });

  it("preserves generated-event workflow progress when the demo is reopened", async () => {
    const savedValues = new Map<string, string>();
    const storage = {
      getItem: (key: string) => savedValues.get(key) ?? null,
      setItem: (key: string, value: string) => savedValues.set(key, value),
    };
    const first = new MockMonitoringClient(undefined, storage);
    const state = await first.applyDemoScenario("physiological_deviation");
    await first.performEventAction(state.targetEventId!, "acknowledge");
    await first.performEventAction(state.targetEventId!, "check");
    await first.resolveEventWithFeedback(state.targetEventId!, {
      outcome: "uncertain",
      actualEventLabel: "Cause not confirmed",
      routine: false,
    });

    const recreated = new MockMonitoringClient(undefined, storage);
    expect(await recreated.getEvent(state.targetEventId!)).toMatchObject({
      status: "resolved",
      resolutionOutcome: "uncertain",
      feedback: { actualEventLabel: "Cause not confirmed" },
    });
  });

  it("reports when a scenario reset cannot be saved for the next visit", async () => {
    let storageFails = false;
    const savedValues = new Map<string, string>();
    const storage = {
      getItem: (key: string) => savedValues.get(key) ?? null,
      setItem: (key: string, value: string) => {
        if (storageFails) throw new Error("Storage unavailable");
        savedValues.set(key, value);
      },
    };
    const client = new MockMonitoringClient(undefined, storage);
    await client.applyDemoScenario("resident_away");
    storageFails = true;

    const reset = await client.resetDemoScenario();

    expect(reset).toMatchObject({ activeScenarioId: null, persistenceAvailable: false });
    expect((await client.getResident("res_7f3a1c")).resident.monitoring.state).toBe("active");
  });
});
