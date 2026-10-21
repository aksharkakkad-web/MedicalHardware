import type { DemoScenarioController } from "@/lib/demo-scenarios";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";
import { DemoWorkspaceClient, DEMO_WORKSPACE_STORAGE_KEY } from "./demo-client";
import type { WorkspaceStorage } from "./demo-client";

/** A source epoch for synthetic fixtures only. Read failures remain visible in workspace.snapshot(). */
export function readDemoSourceObservedAt(
  storage?: WorkspaceStorage,
  fallback = new Date(),
): Date {
  try {
    const raw = storage?.getItem(DEMO_WORKSPACE_STORAGE_KEY);
    if (raw) {
      const saved = JSON.parse(raw) as {
        schemaVersion?: unknown;
        synthetic?: unknown;
        sourceObservedAt?: unknown;
      };
      if (
        saved.schemaVersion === 1 &&
        saved.synthetic === true &&
        typeof saved.sourceObservedAt === "string"
      ) {
        const source = new Date(saved.sourceObservedAt);
        if (
          Number.isFinite(source.getTime()) &&
          source.toISOString() === saved.sourceObservedAt
        )
          return source;
      }
    }
  } catch {
    /* The workspace provider independently reports unreadable saved state. */
  }
  return new Date(fallback);
}

/** Shares one core with the old monitoring/scenario providers and the new workspace provider. */
export function createDemoWorkspaceRuntime(
  options: {
    storage?: WorkspaceStorage;
    now?: () => Date;
  } = {},
) {
  const now = options.now ?? (() => new Date());
  const sourceObservedAt = readDemoSourceObservedAt(options.storage, now());
  const monitoringClient = new MockMonitoringClient(
    () => new Date(sourceObservedAt),
    options.storage,
  );
  const workspaceClient = new DemoWorkspaceClient({
    monitoringClient,
    storage: options.storage,
    now,
    sourceObservedAt,
  });
  async function preserveRecordedScenarioWork() {
    const current = await monitoringClient.getActiveDemoScenario();
    if (!current.targetEventId) return;
    const event = await monitoringClient.getEvent(current.targetEventId);
    if (
      workspaceClient.hasRecordedEventWork(current.targetEventId) ||
      !["open", "detected"].includes(event.status)
    )
      throw new Error(
        "This scenario has recorded response or follow-up history. It cannot be replaced or reset. Keep the care record available.",
      );
  }
  const scenarioController: DemoScenarioController = {
    listDemoScenarios: () => monitoringClient.listDemoScenarios(),
    getActiveDemoScenario: () => monitoringClient.getActiveDemoScenario(),
    async applyDemoScenario(scenarioId) {
      await preserveRecordedScenarioWork();
      const result = await monitoringClient.applyDemoScenario(scenarioId);
      workspaceClient.notifyMonitoringChanged();
      return result;
    },
    async resetDemoScenario() {
      await preserveRecordedScenarioWork();
      const result = await monitoringClient.resetDemoScenario();
      workspaceClient.notifyMonitoringChanged();
      return result;
    },
  };
  return {
    monitoringClient,
    workspaceClient,
    scenarioController,
    sourceObservedAt,
  };
}
