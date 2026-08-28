import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";
import { ResidentDetail } from "./resident-detail";

function renderDetail(residentId: string) {
  const client = new MockMonitoringClient(() => new Date("2026-08-27T18:00:00.000Z"));
  function Wrapper({ children }: { children: ReactNode }) { return <MonitoringClientProvider client={client}>{children}</MonitoringClientProvider>; }
  return render(<ResidentDetail residentId={residentId} />, { wrapper: Wrapper });
}

describe("ResidentDetail", () => {
  it("shows assignment, monitoring truth, and linked event history", async () => {
    renderDetail("res_2c8d4f");
    expect(await screen.findByRole("heading", { name: "Resident B" })).toBeVisible();
    expect(screen.getByText("Room 102", { selector: "dd" })).toBeVisible();
    expect(screen.getAllByText(/unusual activity needs staff review/i)).toHaveLength(2);
    expect(screen.getByText(/previous unusual movement review/i)).toBeVisible();
  });

  it("does not claim safety when a resident cannot load", async () => {
    renderDetail("res_missing");
    expect(await screen.findByRole("alert")).toHaveTextContent(/does not mean monitoring is active or the resident is safe/i);
  });
});
