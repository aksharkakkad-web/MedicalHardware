import type { ResidentOverviewResponse } from "@/lib/monitoring";

export const residentOverviewFixture: ResidentOverviewResponse = {
  schemaVersion: "1.0",
  generatedAt: "2026-08-27T18:00:00Z",
  items: [
    {
      schemaVersion: "1.0",
      residentId: "res_7f3a1c",
      displayLabel: "Resident A",
      roomId: "room_b14e2d",
      roomLabel: "Room 101",
      assignmentStatus: "active",
      monitoring: {
        state: "active",
        reason: "Monitoring is active and data quality is good.",
        lastUpdatedAt: "2026-08-27T17:59:45Z",
      },
      attention: {
        priority: "none",
        headline: "No open attention items",
        openEventCount: 0,
      },
      device: {
        status: "online",
        label: "Room sensor online",
      },
    },
    {
      schemaVersion: "1.0",
      residentId: "res_2c8d4f",
      displayLabel: "Resident B",
      roomId: "room_6a91c3",
      roomLabel: "Room 102",
      assignmentStatus: "active",
      monitoring: {
        state: "active",
        reason: "Monitoring is active with an open event for staff review.",
        lastUpdatedAt: "2026-08-27T17:59:30Z",
      },
      attention: {
        priority: "high",
        headline: "Unusual activity needs staff review",
        openEventCount: 1,
      },
      device: {
        status: "online",
        label: "Room sensor online",
      },
    },
    {
      schemaVersion: "1.0",
      residentId: "res_91be60",
      displayLabel: "Resident C",
      roomId: "room_3d72ab",
      roomLabel: "Room 103",
      assignmentStatus: "active",
      monitoring: {
        state: "paused",
        reason: "Resident is away, so resident-specific monitoring is paused.",
        lastUpdatedAt: "2026-08-27T17:55:00Z",
      },
      attention: {
        priority: "none",
        headline: "No open attention items",
        openEventCount: 0,
      },
      device: {
        status: "online",
        label: "Room sensor online",
      },
    },
    {
      schemaVersion: "1.0",
      residentId: "res_4ab783",
      displayLabel: "Resident D",
      roomId: "room_85cd20",
      roomLabel: "Room 104",
      assignmentStatus: "active",
      monitoring: {
        state: "limited",
        reason:
          "Possible multiple-person presence limits resident-specific monitoring.",
        lastUpdatedAt: "2026-08-27T17:58:10Z",
      },
      attention: {
        priority: "watch",
        headline: "Confirm room occupancy",
        openEventCount: 1,
      },
      device: {
        status: "online",
        label: "Room sensor online",
      },
    },
    {
      schemaVersion: "1.0",
      residentId: "res_d0e519",
      displayLabel: "Resident E",
      roomId: "room_1f64b8",
      roomLabel: "Room 105",
      assignmentStatus: "active",
      monitoring: {
        state: "unavailable",
        reason: "The room device is offline, so current monitoring is unavailable.",
        lastUpdatedAt: "2026-08-27T17:42:00Z",
      },
      attention: {
        priority: "watch",
        headline: "Room device needs attention",
        openEventCount: 1,
      },
      device: {
        status: "offline",
        label: "Room sensor offline",
      },
    },
  ],
};
