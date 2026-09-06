import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DeviceStatus, ResidentOverviewItem } from "@/lib/monitoring";

import { ResidentCard } from "./resident-card";

function residentWithDevice(
  status: DeviceStatus,
  label: string,
): ResidentOverviewItem {
  return {
    schemaVersion: "1.0",
    residentId: `resident-${status}`,
    displayLabel: "Resident Test",
    roomId: "room-test",
    roomLabel: "Room Test",
    assignmentStatus: "active",
    monitoring: {
      state: "limited",
      reason: "Device quality limits current monitoring.",
      lastUpdatedAt: "2026-08-27T18:00:00.000Z",
    },
    attention: {
      priority: "watch",
      headline: "Check the room device",
      openEventCount: 1,
    },
    device: { status, label },
  };
}

describe("ResidentCard device health", () => {
  it("describes a degraded device without calling it offline", () => {
    render(
      <ResidentCard
        resident={residentWithDevice("degraded", "Thermal sensor degraded")}
      />,
    );

    expect(screen.getByLabelText("Device: Degraded")).toHaveAttribute("data-device-status", "degraded");
    expect(screen.queryByLabelText("Device: Offline")).not.toBeInTheDocument();
  });

  it("keeps an unknown device status unknown", () => {
    render(
      <ResidentCard
        resident={residentWithDevice("unknown", "Device status unavailable")}
      />,
    );

    expect(screen.getByLabelText("Device: Unknown")).toHaveAttribute("data-device-status", "unknown");
    expect(screen.queryByLabelText("Device: Offline")).not.toBeInTheDocument();
  });

  it("keeps attention, monitoring, and device as separate facts", () => {
    render(
      <ResidentCard
        resident={residentWithDevice("offline", "Room sensor offline")}
      />,
    );

    const card = screen.getByRole("article");
    const statusFacts = within(card)
      .getAllByLabelText(/^(Attention|Monitoring|Device):/)
      .map((element) => element.getAttribute("aria-label"));

    expect(statusFacts).toEqual([
      "Attention: Watch item",
      "Monitoring: Limited",
      "Device: Offline",
    ]);
  });

  it("shows a healthy online device as a quiet, separate fact", () => {
    render(
      <ResidentCard
        resident={residentWithDevice("online", "Room sensor online")}
      />,
    );

    expect(screen.getByLabelText("Device: Online")).toHaveAttribute("data-device-status", "online");
    expect(screen.queryByText("Room sensor online")).not.toBeInTheDocument();
  });
});

describe("ResidentCard event navigation", () => {
  it("links an attention item to its event details", () => {
    const resident = residentWithDevice("online", "Room sensor online");
    resident.attention.primaryEventId = "evt_test";

    render(<ResidentCard resident={resident} />);

    expect(screen.getByRole("link", { name: /review event/i })).toHaveAttribute(
      "href",
      "/events/evt_test",
    );
  });
});
