import { render, screen } from "@testing-library/react";
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

    expect(screen.getByText("Device degraded")).toBeVisible();
    expect(screen.queryByText("Device offline")).not.toBeInTheDocument();
  });

  it("keeps an unknown device status unknown", () => {
    render(
      <ResidentCard
        resident={residentWithDevice("unknown", "Device status unavailable")}
      />,
    );

    expect(screen.getByText("Device status unknown")).toBeVisible();
    expect(screen.queryByText("Device offline")).not.toBeInTheDocument();
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
