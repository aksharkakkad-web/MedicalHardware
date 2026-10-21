import { describe, expect, it } from "vitest";
import {
  DemoWorkspaceClient,
  DEMO_WORKSPACE_STORAGE_KEY,
  type WorkspaceStorage,
} from "./demo-client";

const now = () => new Date("2026-10-21T15:00:00Z");
function sharedStorage(): WorkspaceStorage {
  const data = new Map<string, string>();
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => {
      data.set(key, value);
    },
  };
}

describe("station configuration conflict protection", () => {
  it("starts seed and approved configurations at one and increments every update and revocation", async () => {
    const client = new DemoWorkspaceClient({ now });
    await client.enterAdminSimulation();
    expect((await client.snapshot()).currentClient.configurationVersion).toBe(
      1,
    );
    const approved = await client.approveClient({
      name: "Synthetic tablet",
      areaIds: ["area_north"],
    });
    expect(approved.configurationVersion).toBe(1);
    const changed = await client.updateClient({
      ...approved,
      name: "Renamed synthetic tablet",
      expectedConfigurationVersion: 1,
    });
    expect(changed.configurationVersion).toBe(2);
    await client.revokeClient(approved.clientId);
    expect(
      (await client.snapshot()).clients.find(
        (station) => station.clientId === approved.clientId,
      )?.configurationVersion,
    ).toBe(3);
  });
  it("rejects an old editor save after another client reduces permissions without restoring the old grant", async () => {
    const storage = sharedStorage();
    const first = new DemoWorkspaceClient({ now, storage });
    const second = new DemoWorkspaceClient({ now, storage });
    await first.enterAdminSimulation();
    await second.enterAdminSimulation();
    const captured = (await first.snapshot()).currentClient;
    await second.updateClient({
      ...captured,
      permissions: ["acknowledge"],
      expectedConfigurationVersion: captured.configurationVersion,
    });
    const before = await first.snapshot();
    await expect(
      first.updateClient({
        ...captured,
        name: "Stale editor name",
        expectedConfigurationVersion: captured.configurationVersion,
      }),
    ).rejects.toThrow(/changed|reload/i);
    const after = await first.snapshot();
    expect(after.currentClient.permissions).toEqual(["acknowledge"]);
    expect(after.currentClient.configurationVersion).toBe(2);
    expect(after.currentClient.name).toBe(captured.name);
    expect(after.version).toBe(before.version);
  });
  it("keeps existing authorized callers that omit the optional expected version valid", async () => {
    const client = new DemoWorkspaceClient({ now });
    await client.enterAdminSimulation();
    const captured = (await client.snapshot()).currentClient;
    const next = await client.updateClient({
      clientId: captured.clientId,
      name: "Legacy authorized caller",
      areaIds: captured.areaIds,
    });
    expect(next.configurationVersion).toBe(2);
    expect(next.permissions).toEqual(captured.permissions);
  });
  it("migrates older synthetic station configuration versions to one without changing explicit grants", async () => {
    const storage = sharedStorage();
    const first = new DemoWorkspaceClient({ now, storage });
    const original = await first.snapshot();
    const saved = JSON.parse(storage.getItem(DEMO_WORKSPACE_STORAGE_KEY)!);
    for (const station of saved.clients) delete station.configurationVersion;
    storage.setItem(DEMO_WORKSPACE_STORAGE_KEY, JSON.stringify(saved));
    const loaded = await new DemoWorkspaceClient({ now, storage }).snapshot();
    expect(loaded.currentClient.configurationVersion).toBe(1);
    expect(loaded.currentClient.permissions).toEqual(
      original.currentClient.permissions,
    );
    expect(loaded.residents).toEqual(original.residents);
  });
});
