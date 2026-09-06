import { render, screen, within } from "@testing-library/react";
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
    expect(screen.getByRole("heading", { name: "Attention queue" })).toBeVisible();
    expect(screen.getByText("Resident A")).toBeVisible();
    expect(screen.getByText(/possible visitor/i)).toBeVisible();
    expect(screen.getByLabelText("Device: Offline")).toBeVisible();
    expect(screen.getAllByLabelText("Attention: Needs attention")).toHaveLength(2);
    const attentionQueue = screen.getByRole("region", { name: "Attention queue" });
    expect(within(attentionQueue).getByRole("heading", { name: "Remaining queue" })).toBeVisible();
    expect(screen.getByRole("link", { name: "View event queue" })).toHaveAttribute("href", "/events");
    expect(within(attentionQueue).getByText("Resident B")).toBeVisible();
    expect(within(attentionQueue).getByLabelText("Attention: Needs attention")).toBeVisible();
    expect(within(attentionQueue).getAllByRole("listitem")[0]).toHaveTextContent("Resident F");
    expect(screen.getByText("6 resident records · 4 need review")).toBeVisible();
    const operationalSummary = screen.getByRole("complementary", { name: "Current clinic context" });
    expect(within(operationalSummary).getAllByRole("region")).toHaveLength(3);
    expect(within(operationalSummary).getByRole("region", { name: "Needs review: 4 of 6 residents" })).toHaveTextContent(
      "Critical0High1Watch3",
    );
    expect(within(operationalSummary).getByRole("region", { name: "Monitoring coverage: 2 of 6 active" })).toHaveTextContent(
      "Active2Limited1Paused1Unavailable2",
    );
    expect(within(operationalSummary).getByRole("region", { name: "Device health: 4 of 6 online" })).toHaveTextContent(
      "Online4Degraded0Offline1Unknown1",
    );
    expect(within(operationalSummary).getByRole("img", { name: "Review distribution: 0 critical, 1 high, 3 watch" })).toBeVisible();
    expect(within(operationalSummary).getByRole("img", { name: "Monitoring distribution: 2 active, 1 limited, 1 paused, 2 unavailable" })).toBeVisible();
    expect(within(operationalSummary).getByRole("img", { name: "Device distribution: 4 online, 0 degraded, 1 offline, 1 unknown" })).toBeVisible();
    expect(within(attentionQueue).getByRole("link", { name: "Review event for Resident B" })).toHaveAttribute(
      "href",
      "/events/evt_unusual_movement_102",
    );
    expect(within(attentionQueue).getByRole("link", { name: "Review resident for Resident F" })).toHaveAttribute(
      "href",
      "/residents/res_assignment_review",
    );

    const residentInventory = screen.getByRole("region", { name: "Resident inventory" });
    const residentRecords = within(residentInventory).getAllByRole("article");
    expect(residentRecords[0]).toHaveTextContent("Resident B");
    expect(residentRecords.at(-1)).toHaveTextContent("Resident C");

    expect(screen.getByLabelText("Device: Offline")).toBeVisible();
    expect(screen.getByLabelText("Device: Unknown")).toBeVisible();
    expect(screen.queryByText("View all events")).not.toBeInTheDocument();
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

  it("keeps the attention surface honest when there are no open items", async () => {
    const response = await new MockMonitoringClient(() => new Date("2026-08-27T18:00:00.000Z")).listResidentOverview();
    const quietItems = response.items.map((resident) => ({
      ...resident,
      attention: {
        priority: "none" as const,
        headline: "No open attention items",
        openEventCount: 0,
      },
    }));

    renderOverview(residentClient(async () => ({ ...response, items: quietItems })));

    expect(await screen.findByRole("heading", { name: "No residents need attention" })).toBeVisible();
    expect(screen.getByText("Current resident records do not contain an open attention item.")).toBeVisible();
    expect(screen.getByRole("link", { name: "View event history" })).toHaveAttribute("href", "/events");
  });
});
