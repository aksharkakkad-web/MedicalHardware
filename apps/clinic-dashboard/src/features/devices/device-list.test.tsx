import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { DeviceList } from "./device-list";

function renderList(authorizedResidentIds?: string[]) {
  const client = new MockMonitoringClient(() => new Date("2026-08-27T18:00:00.000Z"));
  function Wrapper({ children }: { children: ReactNode }) {
    return <MonitoringClientProvider client={client}>{children}</MonitoringClientProvider>;
  }
  return render(<DeviceList authorizedResidentIds={authorizedResidentIds} />, { wrapper: Wrapper });
}

describe("DeviceList", () => {
  it("does not display room units outside approved resident coverage", async () => {
    renderList(["res_7f3a1c"]);
    expect(await screen.findByText("Room unit 101")).toBeVisible();
    expect(screen.queryByText("Room unit 104")).not.toBeInTheDocument();
    expect(screen.queryByText("Unassigned room unit")).not.toBeInTheDocument();
  });
  it("shows honest device states and filters attention work", async () => {
    const user = userEvent.setup();
    renderList();

    expect(await screen.findByRole("heading", { name: "Devices" })).toBeVisible();
    expect(screen.getByText("Room unit 101")).toBeVisible();
    expect(screen.getByText("Unassigned room unit")).toBeVisible();
    expect(screen.getByText("No update yet")).toBeVisible();
    expect(screen.getByRole("link", { name: /Device:\s*Room unit 101.*Assignment:\s*Room 101.*Health:\s*Online.*Last update:.*Setup:\s*Version 2/ })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Needs attention" }));
    expect(screen.getByText("Room unit 105")).toBeVisible();
    expect(screen.queryByText("Room unit 101")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "All" }));
    await user.type(screen.getByRole("textbox", { name: "Search devices" }), "Room 104");
    expect(screen.getByText("Room unit 104")).toBeVisible();
    expect(screen.queryByText("Room unit 105")).not.toBeInTheDocument();
  });
});
