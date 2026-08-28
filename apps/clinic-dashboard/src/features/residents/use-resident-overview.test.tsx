import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import type {
  MonitoringClient,
  ResidentOverviewResponse,
} from "@/lib/monitoring";
import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { useResidentOverview } from "./use-resident-overview";

function withMonitoringClient(client: MonitoringClient) {
  return function TestProvider({ children }: Readonly<{ children: ReactNode }>) {
    return (
      <MonitoringClientProvider client={client}>
        {children}
      </MonitoringClientProvider>
    );
  };
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
    getEvent: (eventId) => fallback.getEvent(eventId),
    performEventAction: (eventId, action) =>
      fallback.performEventAction(eventId, action),
    resolveEventWithFeedback: (eventId, feedback) =>
      fallback.resolveEventWithFeedback(eventId, feedback),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, reject, resolve };
}

const fixedNow = new Date("2026-08-27T18:00:00.000Z");

async function createCompleteResponse(): Promise<ResidentOverviewResponse> {
  return new MockMonitoringClient(() => fixedNow).listResidentOverview();
}

describe("useResidentOverview", () => {
  it("starts in loading and stores the complete resident list", async () => {
    const request = deferred<ResidentOverviewResponse>();
    const client = residentClient(() => request.promise);
    const { result } = renderHook(() => useResidentOverview(), {
      wrapper: withMonitoringClient(client),
    });

    expect(result.current.status).toBe("loading");
    expect(result.current.items).toEqual([]);

    await act(async () => request.resolve(await createCompleteResponse()));

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(result.current.items).toHaveLength(5);
  });

  it("shows a safe error and loads again when retry is used", async () => {
    const response = await createCompleteResponse();
    let requestCount = 0;
    const client = residentClient(
      async () => {
        requestCount += 1;
        if (requestCount === 1) {
          throw new Error("private upstream details");
        }
        return response;
      },
    );
    const { result } = renderHook(() => useResidentOverview(), {
      wrapper: withMonitoringClient(client),
    });

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.items).toEqual([]);
    expect(result.current).toMatchObject({
      message: "Current resident information could not be loaded.",
    });
    expect(JSON.stringify(result.current)).not.toContain(
      "private upstream details",
    );

    act(() => result.current.retry());

    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(requestCount).toBe(2);
    expect(result.current.items).toHaveLength(5);
  });
});
