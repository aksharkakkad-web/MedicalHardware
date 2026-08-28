import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { MonitoringSetup } from "./monitoring-setup";

function renderSetup(residentId = "res_7f3a1c") {
  const client = new MockMonitoringClient(() => new Date("2026-08-28T12:00:00.000Z"));
  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return <MonitoringClientProvider client={client}>{children}</MonitoringClientProvider>;
  }
  return render(<MonitoringSetup residentId={residentId} />, { wrapper: Wrapper });
}

describe("MonitoringSetup", () => {
  it("shows assignment truth, readiness, calibration areas, and demo safety language", async () => {
    renderSetup();

    expect(await screen.findByRole("heading", { name: "Room 101" })).toBeVisible();
    expect(screen.getByText("One resident, one room")).toBeVisible();
    expect(screen.getAllByText("Movement patterns")).toHaveLength(2);
    expect(screen.getAllByText("Breathing-rate patterns")).toHaveLength(2);
    expect(screen.getByText(/not clinical thresholds/i)).toBeVisible();
    expect(screen.getByText("4 of 4 ready")).toBeVisible();
  });

  it("records a focused setup change and preserves the unaffected area", async () => {
    const user = userEvent.setup();
    renderSetup();

    await screen.findByRole("heading", { name: "Room 101" });
    await user.click(screen.getByRole("checkbox", { name: "Movement patterns" }));
    await user.click(screen.getByRole("button", { name: /save and restart/i }));

    expect(await screen.findByText(/only the selected areas restarted/i)).toBeVisible();
    expect(screen.getByText("1 change")).toBeVisible();
    expect(screen.getByText(/other established areas stayed intact/i)).toBeVisible();
    expect(screen.getByText("partial", { selector: "span" })).toBeVisible();
    expect(screen.getByText("3 of 4 ready")).toBeVisible();
  });

  it("blocks setup changes when the assignment conflicts", async () => {
    renderSetup("res_assignment_review");

    expect(await screen.findByText("Assignment needs administrator help")).toBeVisible();
    expect(screen.getAllByText(/authorized administrator resolves the assignment/i)).toHaveLength(2);
    expect(screen.getByRole("button", { name: /save and restart/i })).toBeDisabled();
  });
});
