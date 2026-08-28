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
    expect(screen.getByText("Event opened")).toBeVisible();
  });

  it("moves through acknowledge, check, resolution, and feedback", async () => {
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
    await user.click(screen.getByRole("radio", { name: /confirmed event/i }));
    await user.type(
      screen.getByRole("textbox", { name: /what actually happened/i }),
      "Assisted movement",
    );
    await user.click(screen.getByRole("radio", { name: "Yes" }));
    await user.click(
      screen.getByRole("button", { name: /resolve and save feedback/i }),
    );

    expect(await screen.findByText("Resolved")).toBeVisible();
    expect(screen.getAllByText("Assisted movement")).toHaveLength(2);
    expect(screen.getByText(/history remains available/i)).toBeVisible();
    expect(screen.getByText("Event acknowledged")).toBeVisible();
    expect(screen.getByText("Resident checked")).toBeVisible();
    expect(screen.getByText("Event resolved")).toBeVisible();
    expect(screen.getByText("Feedback saved")).toBeVisible();
  });

  it("requires every resolution answer before saving", async () => {
    const user = userEvent.setup();
    renderEvent();

    await user.click(await screen.findByRole("button", { name: "Acknowledge event" }));
    await user.click(screen.getByRole("button", { name: "Mark resident checked" }));
    await user.click(screen.getByRole("button", { name: /resolve and save feedback/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/choose an outcome/i);
    expect(screen.getByText("Checked")).toBeVisible();
  });

  it("uses a safe unavailable state for an unknown event", async () => {
    renderEvent("evt_missing");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /event information is unavailable/i,
    );
    expect(screen.getByText(/does not mean the resident is safe/i)).toBeVisible();
  });

  it("shows low confidence and unavailable AI without guessing", async () => {
    renderEvent("evt_unknown_pattern_104");

    expect(await screen.findByText("Low confidence")).toBeVisible();
    expect(screen.getByText("Unknown anomaly")).toBeVisible();
    expect(screen.getByText("Explanation unavailable")).toBeVisible();
    expect(screen.getByText(/cannot safely attribute/i)).toBeVisible();
  });

  it("keeps device warnings actionable while AI is pending", async () => {
    renderEvent("evt_device_issue_105");

    expect(await screen.findByText("Data unavailable")).toBeVisible();
    expect(screen.getByText("Explanation pending")).toBeVisible();
    expect(screen.getByText(/still being prepared/i)).toBeVisible();
    expect(screen.getByText("Room sensor offline")).toBeVisible();
  });

  it("shows overdue and related-event history clearly", async () => {
    renderEvent();

    expect(await screen.findByText("Response overdue")).toBeVisible();
    expect(screen.getByText(/appeared 2 times/i)).toBeVisible();
    expect(screen.getByRole("link", { name: "View related event" })).toHaveAttribute(
      "href",
      "/events/evt_previous_movement_102",
    );
  });
});
