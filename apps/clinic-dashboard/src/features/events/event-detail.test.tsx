import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { MonitoringClientProvider } from "@/lib/monitoring/provider";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";

import { EventDetail } from "./event-detail";

function renderEvent(eventId = "evt_unusual_movement_102") {
  const client = new MockMonitoringClient(
    () => new Date("2026-08-27T18:00:00.000Z"),
  );

  function Wrapper({ children }: Readonly<{ children: ReactNode }>) {
    return (
      <MonitoringClientProvider client={client}>
        {children}
      </MonitoringClientProvider>
    );
  }

  return render(<EventDetail eventId={eventId} />, { wrapper: Wrapper });
}

describe("EventDetail", () => {
  it("shows objective evidence without claiming a diagnosis", async () => {
    renderEvent();

    expect(
      await screen.findByRole("heading", {
        name: "Unusual activity needs staff review",
      }),
    ).toBeVisible();
    expect(screen.getByText("Movement changed")).toBeVisible();
    expect(screen.getByText("Position changed")).toBeVisible();
    expect(screen.getByText("Low movement afterward")).toBeVisible();
    expect(screen.getByText(/possible explanation, not a diagnosis/i)).toBeVisible();
  });

  it("moves through acknowledge and resident-check actions", async () => {
    const user = userEvent.setup();
    renderEvent();

    await user.click(
      await screen.findByRole("button", { name: "Acknowledge event" }),
    );

    expect(await screen.findByText("Acknowledged")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Mark resident checked" }),
    );

    expect(await screen.findByText("Checked")).toBeVisible();
    expect(screen.getByText(/resolution and feedback will be added/i)).toBeVisible();
  });

  it("uses a safe unavailable state for an unknown event", async () => {
    renderEvent("evt_missing");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /event information is unavailable/i,
    );
    expect(screen.getByText(/does not mean the resident is safe/i)).toBeVisible();
  });
});
