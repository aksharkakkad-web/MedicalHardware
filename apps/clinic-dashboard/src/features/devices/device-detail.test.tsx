import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { DeviceDetail } from "./device-detail";

function renderDetail(deviceId: string, authorizedResidentIds?: string[]) {
  const client = new MockMonitoringClient(() => new Date("2026-08-27T18:00:00.000Z"));
  function Wrapper({ children }: { children: ReactNode }) {
    return <MonitoringClientProvider client={client}>{children}</MonitoringClientProvider>;
  }
  return render(<DeviceDetail deviceId={deviceId} authorizedResidentIds={authorizedResidentIds} />, { wrapper: Wrapper });
}

describe("DeviceDetail", () => {
  it("does not display an out-of-coverage room unit opened by direct URL", async () => {
    renderDetail("dev_room_104", ["res_7f3a1c"]);
    expect(await screen.findByRole("alert")).toHaveTextContent("outside this shared device’s coverage");
    expect(screen.queryByRole("heading", { name: "Room unit 104" })).not.toBeInTheDocument();
  });
  it("explains limited sources and gives a specific next step", async () => {
    renderDetail("dev_room_104");

    expect(await screen.findByRole("heading", { name: "Room unit 104" })).toBeVisible();
    expect(screen.getByText("Limited monitoring data")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Review source limitations" })).toBeVisible();
    expect(screen.getByText("Wi-Fi sensing")).toBeVisible();
    expect(screen.getByText("Setup check needed")).toBeVisible();
  });

  it("does not claim device state when the requested device is missing", async () => {
    renderDetail("dev_missing");
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot confirm whether monitoring is active/i);
  });
});
