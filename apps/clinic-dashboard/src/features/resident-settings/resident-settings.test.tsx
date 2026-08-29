import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { ResidentSettings } from "./resident-settings";

function renderSettings(residentId = "res_7f3a1c") {
  const client = new MockMonitoringClient(() => new Date("2026-08-28T18:00:00.000Z"));
  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return <MonitoringClientProvider client={client}>{children}</MonitoringClientProvider>;
  }
  return render(<ResidentSettings residentId={residentId} />, { wrapper: Wrapper });
}

describe("ResidentSettings", () => {
  it("separates resident context, calibration, and delivery preferences", async () => {
    renderSettings();

    expect(await screen.findByRole("heading", { name: "Context & notifications" })).toBeVisible();
    expect(screen.getByText("Assisted standing is common after breakfast.")).toBeVisible();
    expect(screen.getByText("Physical therapy usually happens on Tuesday afternoons.")).toBeVisible();
    expect(screen.getByText(/do not directly change the numerical calibration/i)).toBeVisible();
    expect(screen.getByText(/high and critical events always stay visible/i)).toBeVisible();
    expect(screen.getByText("Memory version 3")).toBeVisible();
  });

  it("adds resident context through the mock client", async () => {
    const user = userEvent.setup();
    renderSettings("res_2c8d4f");

    const field = await screen.findByRole("textbox", { name: "Add useful context" });
    await user.type(field, "Assisted walking is common after lunch.");
    await user.click(screen.getByRole("button", { name: "Add context" }));

    expect(await screen.findByText("Assisted walking is common after lunch.")).toBeVisible();
    expect(screen.getByText(/calibration and warning rules were not changed/i)).toBeVisible();
    expect(screen.getByText("Memory version 1")).toBeVisible();
  });

  it("corrects an entry while keeping its original history", async () => {
    const user = userEvent.setup();
    renderSettings();

    const entry = (await screen.findByText("Assisted standing is common after breakfast.")).closest("article");
    expect(entry).not.toBeNull();
    await user.click(within(entry!).getByRole("button", { name: "Correct" }));
    const corrected = within(entry!).getByRole("textbox", { name: "Corrected context" });
    await user.clear(corrected);
    await user.type(corrected, "Assisted standing is common after morning medication.");
    await user.type(within(entry!).getByRole("textbox", { name: "Reason for correction" }), "The routine changed.");
    await user.click(within(entry!).getByRole("button", { name: "Save correction" }));

    expect(await screen.findByText("Assisted standing is common after morning medication.")).toBeVisible();
    expect(screen.getByText(/original context remains in history/i)).toBeVisible();
    expect(screen.getByText("Retired because: The routine changed.")).toBeVisible();
  });

  it("retires context without deleting it", async () => {
    const user = userEvent.setup();
    renderSettings();

    const entry = (await screen.findByText("Physical therapy usually happens on Tuesday afternoons.")).closest("article");
    expect(entry).not.toBeNull();
    await user.click(within(entry!).getByRole("button", { name: "Retire" }));
    await user.type(within(entry!).getByRole("textbox", { name: "Reason for retirement" }), "The schedule ended.");
    await user.click(within(entry!).getByRole("button", { name: "Retire context" }));

    expect(await screen.findByText(/history remains available/i)).toBeVisible();
    expect(screen.getByText("Retired because: The schedule ended.")).toBeVisible();
    expect(screen.getByText("Physical therapy usually happens on Tuesday afternoons.")).toBeVisible();
  });

  it("saves delivery choices without hiding urgent dashboard work", async () => {
    const user = userEvent.setup();
    renderSettings();

    const critical = await screen.findByRole("checkbox", { name: /critical events/i });
    await user.click(critical);
    await user.click(screen.getByRole("button", { name: "Save delivery preferences" }));

    expect(await screen.findByText("Future delivery preferences saved.")).toBeVisible();
    expect(screen.getByText(/high and critical events remain visible here/i)).toBeVisible();
    expect(screen.getByText("Version 2")).toBeVisible();
  });

  it("shows an honest first-save state when no preferences or context exist", async () => {
    renderSettings("res_assignment_review");

    expect(await screen.findByText("No choices have been saved yet")).toBeVisible();
    expect(screen.getByText("No resident context has been saved")).toBeVisible();
    expect(screen.getByText("Memory version 0")).toBeVisible();
    expect(screen.getByText("Not saved", { selector: "span" })).toBeVisible();
  });
});
