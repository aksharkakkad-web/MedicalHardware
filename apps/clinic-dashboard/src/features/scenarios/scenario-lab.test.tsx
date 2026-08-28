import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { DemoScenarioProvider } from "@/lib/demo-scenarios";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { ScenarioLab } from "./scenario-lab";

function renderLab(client: MockMonitoringClient | null = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"))) {
  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return <DemoScenarioProvider controller={client}>{children}</DemoScenarioProvider>;
  }
  return render(<ScenarioLab />, { wrapper: Wrapper });
}

describe("ScenarioLab", () => {
  it("runs a walkthrough, shows the affected screen, and resets the demo", async () => {
    const user = userEvent.setup();
    renderLab();

    expect(await screen.findByRole("heading", { name: "Scenario Lab" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Baseline demo" })).toBeVisible();
    expect(screen.getAllByRole("button", { name: /^Run / })).toHaveLength(4);

    await user.click(screen.getByRole("button", { name: "Run resident leaves the room" }));
    expect(await screen.findByRole("heading", { name: "Resident leaves the room active" })).toBeVisible();
    expect(screen.getByText("Resident A shows monitoring paused")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open Resident A" })).toHaveAttribute("href", "/residents/res_7f3a1c");

    await user.click(screen.getByRole("button", { name: "Reset demo" }));
    expect(await screen.findByRole("heading", { name: "Baseline demo" })).toBeVisible();
  });

  it("links event scenarios to their generated event", async () => {
    const user = userEvent.setup();
    renderLab();

    await user.click(await screen.findByRole("button", { name: "Run physiological pattern changes" }));

    expect(await screen.findByRole("heading", { name: "Physiological pattern changes active" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open generated event" })).toHaveAttribute("href", "/events/evt_demo_physiological_101");
    expect(screen.getByText(/does not identify a diagnosis/i)).toBeVisible();
  });

  it("explains when demo controls are unavailable", async () => {
    renderLab(null);

    expect(await screen.findByRole("alert")).toHaveTextContent(/only available with synthetic demo data/i);
  });
});
