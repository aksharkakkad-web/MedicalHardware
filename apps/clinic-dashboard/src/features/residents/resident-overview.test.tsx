import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type {
  MonitoringClient,
  ResidentOverviewResponse,
} from "@/lib/monitoring";
import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { ResidentOverview } from "./resident-overview";

function renderOverview(client: MonitoringClient) {
  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return (
      <MonitoringClientProvider client={client}>
        {children}
      </MonitoringClientProvider>
    );
  }

  return render(<ResidentOverview />, { wrapper: Wrapper });
}

function residentClient(
  listResidentOverview: MonitoringClient["listResidentOverview"],
): MonitoringClient {
  const fallback = new MockMonitoringClient();
  return {
    listDevices: () => fallback.listDevices(),
    getDevice: (deviceId) => fallback.getDevice(deviceId),
    listResidentOverview,
    listEvents: () => fallback.listEvents(),
    getResident: (residentId) => fallback.getResident(residentId),
    getResidentMonitoringSetup: (residentId) => fallback.getResidentMonitoringSetup(residentId),
    recordSetupChange: (residentId, input) => fallback.recordSetupChange(residentId, input),
    getNotificationPreferences: (residentId) => fallback.getNotificationPreferences(residentId),
    updateNotificationPreferences: (residentId, input) => fallback.updateNotificationPreferences(residentId, input),
    getResidentMemory: (residentId) => fallback.getResidentMemory(residentId),
    addMemoryEntry: (residentId, input) => fallback.addMemoryEntry(residentId, input),
    correctMemoryEntry: (residentId, entryId, input) => fallback.correctMemoryEntry(residentId, entryId, input),
    retireMemoryEntry: (residentId, entryId, input) => fallback.retireMemoryEntry(residentId, entryId, input),
    getEvent: (eventId) => fallback.getEvent(eventId),
    performEventAction: (eventId, action) =>
      fallback.performEventAction(eventId, action),
    resolveEventWithFeedback: (eventId, feedback) =>
      fallback.resolveEventWithFeedback(eventId, feedback),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe("ResidentOverview", () => {
  it("shows the honest monitoring situations", async () => {
    renderOverview(
      new MockMonitoringClient(() => new Date("2026-08-27T18:00:00.000Z")),
    );

    expect(
      await screen.findByRole("heading", { name: /clinic overview/i }),
    ).toBeVisible();
    expect(screen.getByText("Resident A")).toBeVisible();
    expect(screen.getByText(/possible visitor/i)).toBeVisible();
    expect(screen.getByText(/device offline/i)).toBeVisible();
    expect(screen.getByText(/^needs attention$/i)).toBeVisible();
  });

  it("shows a neutral loading state", () => {
    const request = deferred<ResidentOverviewResponse>();
    renderOverview(residentClient(() => request.promise));

    expect(
      screen.getByRole("status", { name: /loading resident information/i }),
    ).toBeVisible();
  });

  it("does not describe an empty result as safe", async () => {
    renderOverview(residentClient(
      async () => {
        return {
          schemaVersion: "1.0",
          generatedAt: "2026-08-27T18:00:00.000Z",
          items: [],
        };
      },
    ));

    expect(await screen.findByText(/no resident information/i)).toBeVisible();
    expect(screen.queryByText(/everyone is safe/i)).not.toBeInTheDocument();
  });

  it("offers retry when current information cannot load", async () => {
    renderOverview(residentClient(
      async () => {
        throw new Error("offline");
      },
    ));

    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByRole("button", { name: /retry/i })).toBeVisible();
  });
});
