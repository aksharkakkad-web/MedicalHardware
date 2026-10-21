import { describe, expect, it } from "vitest";
import {
  createDemoWorkspaceRuntime,
  readDemoSourceObservedAt,
} from "./runtime";
import { DEMO_WORKSPACE_STORAGE_KEY } from "./demo-client";
describe("shared demo runtime source epoch", () => {
  it("initializes the monitoring core and workspace at the same persisted source epoch", async () => {
    const data = new Map<string, string>();
    const storage = {
      getItem: (key: string) => data.get(key) ?? null,
      setItem: (key: string, value: string) => {
        data.set(key, value);
      },
    };
    const first = createDemoWorkspaceRuntime({
      storage,
      now: () => new Date("2026-10-21T15:00:00Z"),
    });
    const original = await first.workspaceClient.snapshot();
    const second = createDemoWorkspaceRuntime({
      storage,
      now: () => new Date("2026-10-22T15:00:00Z"),
    });
    const next = await second.workspaceClient.snapshot();
    expect(next.sourceObservedAt).toBe(original.sourceObservedAt);
    expect(next.events.map((e) => e.createdAt)).toEqual(
      original.events.map((e) => e.createdAt),
    );
    expect(
      (await second.monitoringClient.listResidentOverview()).generatedAt,
    ).toBe(original.sourceObservedAt);
  });
  it("uses a safe fallback epoch without hiding an unreadable workspace error", async () => {
    const storage = {
      getItem: (key: string) =>
        key === DEMO_WORKSPACE_STORAGE_KEY ? "{broken" : null,
      setItem: () => undefined,
    };
    const fallback = new Date("2026-10-21T15:00:00Z");
    expect(readDemoSourceObservedAt(storage, fallback)).toEqual(fallback);
    const runtime = createDemoWorkspaceRuntime({
      storage,
      now: () => fallback,
    });
    await expect(runtime.workspaceClient.snapshot()).rejects.toThrow(
      /saved.*read/i,
    );
  });
});
describe("scenario changes use the same care workspace", () => {
  it("publishes scenario updates and protects recorded response history from reset", async () => {
    const runtime = createDemoWorkspaceRuntime({
      now: () => new Date("2026-10-21T15:00:00Z"),
    });
    let notifications = 0;
    runtime.workspaceClient.subscribe(() => {
      notifications++;
    });
    const state = await runtime.scenarioController.applyDemoScenario(
      "possible_multi_person",
    );
    expect(notifications).toBe(1);
    expect(
      (await runtime.workspaceClient.snapshot()).residents.find(
        (r) => r.residentId === state.targetResidentId,
      )?.monitoring.state,
    ).toBe("limited");
    await runtime.workspaceClient.acknowledgeEvent(state.targetEventId!);
    await expect(
      runtime.scenarioController.resetDemoScenario(),
    ).rejects.toThrow(/history|response/i);
    expect(
      (await runtime.workspaceClient.snapshot()).events.find(
        (e) => e.eventId === state.targetEventId,
      )?.status,
    ).toBe("acknowledged");
  });
});
