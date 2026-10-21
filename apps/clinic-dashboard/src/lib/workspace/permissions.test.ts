import { describe, expect, it } from "vitest";
import {
  DemoWorkspaceClient,
  DEMO_WORKSPACE_STORAGE_KEY,
  type WorkspaceStorage,
} from "./demo-client";
import { hasWorkspacePermission, WORKSPACE_PERMISSIONS } from "./permissions";
import type { WorkspacePermission } from "./types";

const now = () => new Date("2026-10-21T15:00:00Z");
const eventId = "evt_unusual_movement_102";
function sharedStorage(): WorkspaceStorage {
  const saved = new Map<string, string>();
  return {
    getItem: (key) => saved.get(key) ?? null,
    setItem: (key, value) => {
      saved.set(key, value);
    },
  };
}
async function viewOnly() {
  const client = new DemoWorkspaceClient({ now });
  await client.acknowledgeEvent(eventId);
  await client.recordCheck(eventId, { outcome: "no_concern_observed" });
  const followUp = await client.addFollowUp({
    residentId: "res_2c8d4f",
    text: "Synthetic follow-up",
  });
  await client.enterAdminSimulation();
  const viewer = await client.approveClient({
    name: "North view-only tablet",
    areaIds: ["area_north"],
  });
  await client.selectDemoClient(viewer.clientId);
  await client.leaveAdminSimulation();
  return { client, followUp };
}

describe("explicit synthetic station action grants", () => {
  it("seeds the main station explicitly and excludes resolution from the phone grant", async () => {
    const station = new DemoWorkspaceClient({ now });
    expect((await station.snapshot()).currentClient.permissions).toEqual(
      WORKSPACE_PERMISSIONS,
    );
    const phone = new DemoWorkspaceClient({ now, clientId: "demo_phone_02" });
    const snapshot = await phone.snapshot();
    expect(hasWorkspacePermission(snapshot, "record_check")).toBe(true);
    expect(hasWorkspacePermission(snapshot, "resolve_concern")).toBe(false);
    expect(hasWorkspacePermission(null, "acknowledge")).toBe(false);
    await phone.acknowledgeEvent(eventId);
    await phone.recordCheck(eventId, { outcome: "no_concern_observed" });
    await expect(
      phone.resolveEvent(eventId, {
        outcome: "false_positive",
        actualEventLabel: "Synthetic routine",
        routine: false,
      }),
    ).rejects.toThrow(/permitted|permission|grant/i);
    expect(
      (await phone.snapshot()).events.find((event) => event.eventId === eventId)
        ?.status,
    ).toBe("checked");
  });
  it("approves omitted permissions as view-only while keeping covered concerns and readings visible", async () => {
    const { client } = await viewOnly();
    const snapshot = await client.snapshot();
    expect(snapshot.currentClient.permissions).toEqual([]);
    expect(snapshot.residents).toHaveLength(3);
    expect(snapshot.events.length).toBeGreaterThan(0);
    expect(
      snapshot.measurements.some((measurement) => measurement.value !== null),
    ).toBe(true);
  });
  it.each<WorkspacePermission>([...WORKSPACE_PERMISSIONS])(
    "enforces %s in the service for a view-only station",
    async (permission) => {
      const { client, followUp } = await viewOnly();
      const actions: Record<WorkspacePermission, () => Promise<unknown>> = {
        acknowledge: () => client.acknowledgeEvent(eventId),
        record_check: () =>
          client.recordCheck(eventId, { outcome: "no_concern_observed" }),
        resolve_concern: () =>
          client.resolveEvent(eventId, {
            outcome: "false_positive",
            actualEventLabel: "Synthetic routine",
            routine: false,
          }),
        add_follow_up: () =>
          client.addFollowUp({
            residentId: "res_2c8d4f",
            text: "Synthetic follow-up",
          }),
        update_follow_up: () => client.completeFollowUp(followUp.followUpId),
        report_context: () =>
          client.addContext("res_2c8d4f", { text: "Synthetic observation" }),
      };
      await expect(actions[permission]()).rejects.toThrow(
        /permitted|permission|grant/i,
      );
      if (permission === "update_follow_up")
        await expect(
          client.handOverFollowUp(followUp.followUpId, "Synthetic handover"),
        ).rejects.toThrow(/permitted|permission|grant/i);
    },
  );
  it("does not give clinical command authority to simulated administration and removes its context exception on logout", async () => {
    const { client } = await viewOnly();
    await client.enterAdminSimulation();
    const context = await client.addContext("res_2c8d4f", {
      text: "Synthetic administrator observation",
    });
    expect(context.reviewStatus).toBe("needs_review");
    await expect(
      client.recordCheck(eventId, { outcome: "no_concern_observed" }),
    ).rejects.toThrow(/permitted|permission|grant/i);
    await client.leaveAdminSimulation();
    await expect(
      client.addContext("res_2c8d4f", {
        text: "Synthetic routine observation",
      }),
    ).rejects.toThrow(/permitted|permission|grant/i);
    expect((await client.snapshot()).residents).toHaveLength(3);
  });
  it("preserves permissions on omitted edits and immediately applies a reduction to cached retries and other clients", async () => {
    const storage = sharedStorage();
    const admin = new DemoWorkspaceClient({ now, storage });
    const staff = new DemoWorkspaceClient({ now, storage });
    await staff.acknowledgeEvent(eventId, "previous-ack");
    await admin.enterAdminSimulation();
    const station = (await admin.snapshot()).currentClient;
    await admin.updateClient({
      clientId: station.clientId,
      name: "Renamed station",
      areaIds: station.areaIds,
    });
    expect((await staff.snapshot()).currentClient.permissions).toEqual(
      WORKSPACE_PERMISSIONS,
    );
    await admin.updateClient({ ...station, permissions: [] });
    expect((await staff.snapshot()).currentClient.permissions).toEqual([]);
    await expect(
      staff.acknowledgeEvent(eventId, "previous-ack"),
    ).rejects.toThrow(/permitted|permission|grant/i);
    await expect(
      staff.recordCheck(eventId, { outcome: "no_concern_observed" }),
    ).rejects.toThrow(/permitted|permission|grant/i);
  });
  it("migrates older stored clients with missing grants to view-only without changing existing care records", async () => {
    const storage = sharedStorage();
    const original = new DemoWorkspaceClient({ now, storage });
    await original.acknowledgeEvent(eventId);
    const old = JSON.parse(storage.getItem(DEMO_WORKSPACE_STORAGE_KEY)!);
    for (const station of old.clients) delete station.permissions;
    storage.setItem(DEMO_WORKSPACE_STORAGE_KEY, JSON.stringify(old));
    const loaded = new DemoWorkspaceClient({ now, storage });
    const snapshot = await loaded.snapshot();
    expect(snapshot.currentClient.permissions).toEqual([]);
    expect(snapshot.residents).toHaveLength(6);
    expect(
      snapshot.events.find((event) => event.eventId === eventId)?.status,
    ).toBe("acknowledged");
    await expect(
      loaded.recordCheck(eventId, { outcome: "no_concern_observed" }),
    ).rejects.toThrow(/permitted|permission|grant/i);
  });
});
