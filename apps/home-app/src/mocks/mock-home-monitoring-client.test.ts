import { beforeEach, describe, expect, it } from "vitest";
import { MockHomeMonitoringClient, type HomeStorage } from "./mock-home-monitoring-client";

class MemoryStorage implements HomeStorage {
  values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
}

describe("MockHomeMonitoringClient", () => {
  let storage: MemoryStorage;
  let client: MockHomeMonitoringClient;

  beforeEach(() => {
    storage = new MemoryStorage();
    client = new MockHomeMonitoringClient(storage);
  });

  it("returns cloned family-safe overview data", async () => {
    const first = await client.getOverview();
    first.lovedOne.status.headline = "changed outside";
    const second = await client.getOverview();
    expect(second.lovedOne.status.headline).toBe("Monitoring looks steady");
    expect(JSON.stringify(second)).not.toMatch(/sensor|confidence|diagnos/i);
  });

  it("returns a plain-language update with explicit uncertainty", async () => {
    const update = await client.getUpdate("home_evt_unusual_001");
    expect(update?.observations).toHaveLength(2);
    expect(update?.limitation).toMatch(/cannot tell the exact cause/i);
    expect(update?.interpretation).toMatch(/not a diagnosis/i);
    expect(JSON.stringify(update)).not.toMatch(/radar|thermal|wifi csi|confidence:|resolve|escalate/i);
  });

  it("validates and persists feedback across clients", async () => {
    await expect(client.saveUpdateFeedback("home_evt_unusual_001", {
      outcome: "expected", note: "x".repeat(241), shouldRememberRoutine: false,
    })).rejects.toThrow(/240/);
    await expect(client.saveUpdateFeedback("home_evt_unusual_001", {
      outcome: "expected", note: "", shouldRememberRoutine: true,
    })).rejects.toThrow(/short note/i);
    await expect(client.saveUpdateFeedback("home_evt_unusual_001", {
      outcome: "expected", note: "x".repeat(161), shouldRememberRoutine: true,
    })).rejects.toThrow(/160/);
    expect((await client.getUpdate("home_evt_unusual_001"))?.feedback).toBeNull();
    expect((await client.getRoutines()).entries).toHaveLength(3);

    const saved = await client.saveUpdateFeedback("home_evt_unusual_001", {
      outcome: "expected", note: " Evening stretching ", shouldRememberRoutine: true,
    });
    expect(saved.feedback?.note).toBe("Evening stretching");
    const reloaded = await new MockHomeMonitoringClient(storage).getUpdate("home_evt_unusual_001");
    expect(reloaded?.feedback?.shouldRememberRoutine).toBe(true);
    const routines = await new MockHomeMonitoringClient(storage).getRoutines();
    expect(routines.entries[0].description).toBe("Evening stretching");
  });

  it("adds and retires routines with version checks and preserved history", async () => {
    const initial = await client.getRoutines();
    const added = await client.addRoutine({ expectedVersion: initial.version, description: "  Takes a short walk after lunch  " });
    expect(added.version).toBe(initial.version + 1);
    expect(added.entries[0].description).toBe("Takes a short walk after lunch");
    await expect(client.addRoutine({ expectedVersion: initial.version, description: "Late" })).rejects.toThrow(/changed/);

    const retired = await client.retireRoutine(added.entries[0].routineId, {
      expectedVersion: added.version, reason: " Routine changed ",
    });
    expect(retired.entries.find((entry) => entry.routineId === added.entries[0].routineId)).toMatchObject({
      status: "retired", retirementReason: "Routine changed",
    });
  });

  it("falls back safely when stored JSON is malformed", async () => {
    storage.setItem("adaptive-care:home-routines:v1", "not-json");
    const routines = await client.getRoutines();
    expect(routines.entries.length).toBeGreaterThan(0);
  });

  it("falls back safely when stored JSON has the wrong shape", async () => {
    storage.setItem("adaptive-care:home-routines:v1", JSON.stringify({ version: 1 }));
    storage.setItem("adaptive-care:home-feedback:v1", JSON.stringify({ bad: { outcome: "expected" } }));
    const recreated = new MockHomeMonitoringClient(storage);
    expect((await recreated.getRoutines()).entries).toHaveLength(3);
    expect((await recreated.getUpdate("home_evt_unusual_001"))?.feedback).toBeNull();
  });

  it("rejects impossible stored dates and inconsistent lifecycle fields", async () => {
    const badDates = structuredClone((await client.getRoutines()));
    badDates.entries[0].createdAt = "not-a-date";
    storage.setItem("adaptive-care:home-routines:v1", JSON.stringify(badDates));
    expect((await new MockHomeMonitoringClient(storage).getRoutines()).entries).toHaveLength(3);

    const badLifecycle = structuredClone((await client.getRoutines()));
    badLifecycle.entries[0].retiredAt = "2026-08-28T12:00:00.000Z";
    storage.setItem("adaptive-care:home-routines:v1", JSON.stringify(badLifecycle));
    expect((await new MockHomeMonitoringClient(storage).getRoutines()).entries[0].retiredAt).toBeNull();
  });
});
