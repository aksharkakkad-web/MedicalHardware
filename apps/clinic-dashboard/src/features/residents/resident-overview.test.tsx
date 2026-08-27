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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe("ResidentOverview", () => {
  it("shows the five honest monitoring situations", async () => {
    renderOverview(
      new MockMonitoringClient(() => new Date("2026-08-27T18:00:00.000Z")),
    );

    expect(
      await screen.findByRole("heading", { name: /resident overview/i }),
    ).toBeVisible();
    expect(screen.getByText("Resident A")).toBeVisible();
    expect(screen.getByText(/possible visitor/i)).toBeVisible();
    expect(screen.getByText(/device offline/i)).toBeVisible();
    expect(screen.getByText(/^needs attention$/i)).toBeVisible();
  });

  it("shows a neutral loading state", () => {
    const request = deferred<ResidentOverviewResponse>();
    renderOverview({ listResidentOverview: () => request.promise });

    expect(
      screen.getByRole("status", { name: /loading resident information/i }),
    ).toBeVisible();
  });

  it("does not describe an empty result as safe", async () => {
    renderOverview({
      async listResidentOverview() {
        return {
          schemaVersion: "1.0",
          generatedAt: "2026-08-27T18:00:00.000Z",
          items: [],
        };
      },
    });

    expect(await screen.findByText(/no resident information/i)).toBeVisible();
    expect(screen.queryByText(/everyone is safe/i)).not.toBeInTheDocument();
  });

  it("offers retry when current information cannot load", async () => {
    renderOverview({
      async listResidentOverview() {
        throw new Error("offline");
      },
    });

    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByRole("button", { name: /retry/i })).toBeVisible();
  });
});
