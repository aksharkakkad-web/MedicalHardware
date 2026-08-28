import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { DemoScenarioProvider } from "@/lib/demo-scenarios";
import type { DemoScenarioController } from "@/lib/demo-scenarios";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { ScenarioLab } from "./scenario-lab";

function renderLab(client: DemoScenarioController | null = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"))) {
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

  it("announces loading and scenario action errors", async () => {
    const pendingController: DemoScenarioController = {
      listDemoScenarios: () => new Promise(() => undefined),
      getActiveDemoScenario: () => new Promise(() => undefined),
      applyDemoScenario: () => new Promise(() => undefined),
      resetDemoScenario: () => new Promise(() => undefined),
    };
    const loading = renderLab(pendingController);
    expect(screen.getByRole("status")).toHaveTextContent(/opening scenario lab/i);
    loading.unmount();

    const client = new MockMonitoringClient();
    client.applyDemoScenario = async () => { throw new Error("Synthetic scenario failed safely."); };
    const user = userEvent.setup();
    renderLab(client);
    await user.click(await screen.findByRole("button", { name: "Run resident leaves the room" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Synthetic scenario failed safely.");
  });

  it("states when reset only applies to the current visit", async () => {
    const client = new MockMonitoringClient(undefined, {
      getItem: () => null,
      setItem: () => { throw new Error("Storage unavailable"); },
    });
    const user = userEvent.setup();
    renderLab(client);

    await user.click(await screen.findByRole("button", { name: "Run resident leaves the room" }));
    await user.click(await screen.findByRole("button", { name: "Reset demo" }));

    expect(await screen.findByText(/baseline restored for this visit/i)).toBeVisible();
  });
});
