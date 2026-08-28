import type { ClinicDeviceListResponse } from "@/lib/monitoring";

function timestampBefore(now: Date, offsetMs: number): string {
  return new Date(now.getTime() - offsetMs).toISOString();
}

export function createDeviceListFixture(now: Date): ClinicDeviceListResponse {
  return {
    schemaVersion: "1.0",
    generatedAt: now.toISOString(),
    items: [
      {
        schemaVersion: "1.0",
        deviceId: "dev_room_101",
        displayLabel: "Northstar 101",
        modelLabel: "Adaptive Care Room Hub",
        roomId: "room_b14e2d",
        roomLabel: "Room 101",
        residentId: "res_7f3a1c",
        residentLabel: "Resident A",
        assignmentStatus: "assigned",
        health: {
          status: "online",
          dataAvailability: "available",
          summary: "All three sensing sources are reporting normally.",
          lastSeenAt: timestampBefore(now, 15_000),
        },
        setup: {
          version: 2,
          state: "ready",
          updatedAt: timestampBefore(now, 12 * 24 * 60 * 60_000),
        },
        sources: [
          { sourceId: "radar", label: "Radar", status: "available", detail: "Movement and position features are available.", lastSeenAt: timestampBefore(now, 15_000) },
          { sourceId: "thermal", label: "Thermal", status: "available", detail: "Thermal features are available.", lastSeenAt: timestampBefore(now, 18_000) },
          { sourceId: "wifi", label: "Wi-Fi sensing", status: "available", detail: "Wi-Fi motion features are available.", lastSeenAt: timestampBefore(now, 17_000) },
        ],
      },
      {
        schemaVersion: "1.0",
        deviceId: "dev_room_102",
        displayLabel: "Northstar 102",
        modelLabel: "Adaptive Care Room Hub",
        roomId: "room_6a91c3",
        roomLabel: "Room 102",
        residentId: "res_2c8d4f",
        residentLabel: "Resident B",
        assignmentStatus: "assigned",
        health: {
          status: "buffering",
          dataAvailability: "limited",
          summary: "The device is online but temporarily storing updates before retrying delivery.",
          lastSeenAt: timestampBefore(now, 44_000),
        },
        setup: {
          version: 1,
          state: "ready",
          updatedAt: timestampBefore(now, 28 * 24 * 60 * 60_000),
        },
        sources: [
          { sourceId: "radar", label: "Radar", status: "available", detail: "Movement and position features are available.", lastSeenAt: timestampBefore(now, 44_000) },
          { sourceId: "thermal", label: "Thermal", status: "available", detail: "Thermal features are available.", lastSeenAt: timestampBefore(now, 45_000) },
          { sourceId: "wifi", label: "Wi-Fi sensing", status: "limited", detail: "Recent packages are buffered while delivery retries.", lastSeenAt: timestampBefore(now, 46_000) },
        ],
      },
      {
        schemaVersion: "1.0",
        deviceId: "dev_room_103",
        displayLabel: "Northstar 103",
        modelLabel: "Adaptive Care Room Hub",
        roomId: "room_3d72ab",
        roomLabel: "Room 103",
        residentId: "res_91be60",
        residentLabel: "Resident C",
        assignmentStatus: "assigned",
        health: {
          status: "online",
          dataAvailability: "available",
          summary: "The room hub is online. Resident-specific monitoring is paused because the resident is away.",
          lastSeenAt: timestampBefore(now, 24_000),
        },
        setup: {
          version: 3,
          state: "ready",
          updatedAt: timestampBefore(now, 5 * 24 * 60 * 60_000),
        },
        sources: [
          { sourceId: "radar", label: "Radar", status: "available", detail: "Room-level features are available.", lastSeenAt: timestampBefore(now, 24_000) },
          { sourceId: "thermal", label: "Thermal", status: "available", detail: "Room-level features are available.", lastSeenAt: timestampBefore(now, 26_000) },
          { sourceId: "wifi", label: "Wi-Fi sensing", status: "available", detail: "Room-level features are available.", lastSeenAt: timestampBefore(now, 25_000) },
        ],
      },
      {
        schemaVersion: "1.0",
        deviceId: "dev_room_104",
        displayLabel: "Northstar 104",
        modelLabel: "Adaptive Care Room Hub",
        roomId: "room_85cd20",
        roomLabel: "Room 104",
        residentId: "res_4ab783",
        residentLabel: "Resident D",
        assignmentStatus: "assigned",
        health: {
          status: "degraded",
          dataAvailability: "limited",
          summary: "Radar and Wi-Fi sensing are limited. The interface does not guess resident-specific activity.",
          lastSeenAt: timestampBefore(now, 110_000),
        },
        setup: {
          version: 1,
          state: "needs_attention",
          updatedAt: timestampBefore(now, 46 * 24 * 60 * 60_000),
        },
        sources: [
          { sourceId: "radar", label: "Radar", status: "limited", detail: "Movement features are noisy and should not be treated as precise.", lastSeenAt: timestampBefore(now, 112_000) },
          { sourceId: "thermal", label: "Thermal", status: "available", detail: "Thermal features are available.", lastSeenAt: timestampBefore(now, 110_000) },
          { sourceId: "wifi", label: "Wi-Fi sensing", status: "limited", detail: "Room occupancy appears ambiguous.", lastSeenAt: timestampBefore(now, 116_000) },
        ],
      },
      {
        schemaVersion: "1.0",
        deviceId: "dev_room_105",
        displayLabel: "Northstar 105",
        modelLabel: "Adaptive Care Room Hub",
        roomId: "room_1f64b8",
        roomLabel: "Room 105",
        residentId: "res_d0e519",
        residentLabel: "Resident E",
        assignmentStatus: "assigned",
        health: {
          status: "offline",
          dataAvailability: "unavailable",
          summary: "No room sensor package has arrived for 18 minutes. Current monitoring is unavailable.",
          lastSeenAt: timestampBefore(now, 18 * 60_000),
        },
        setup: {
          version: 1,
          state: "needs_attention",
          updatedAt: timestampBefore(now, 31 * 24 * 60 * 60_000),
        },
        sources: [
          { sourceId: "radar", label: "Radar", status: "unavailable", detail: "No recent source update is available.", lastSeenAt: timestampBefore(now, 18 * 60_000) },
          { sourceId: "thermal", label: "Thermal", status: "unavailable", detail: "No recent source update is available.", lastSeenAt: timestampBefore(now, 18 * 60_000) },
          { sourceId: "wifi", label: "Wi-Fi sensing", status: "unavailable", detail: "No recent source update is available.", lastSeenAt: timestampBefore(now, 18 * 60_000) },
        ],
      },
      {
        schemaVersion: "1.0",
        deviceId: "dev_staging_01",
        displayLabel: "Northstar staging unit",
        modelLabel: "Adaptive Care Room Hub",
        roomId: null,
        roomLabel: null,
        residentId: null,
        residentLabel: null,
        assignmentStatus: "unassigned",
        health: {
          status: "unavailable",
          dataAvailability: "not_yet_available",
          summary: "This device has not been assigned to a monitored room, so monitoring is not available.",
          lastSeenAt: null,
        },
        setup: {
          version: 0,
          state: "not_started",
          updatedAt: timestampBefore(now, 2 * 24 * 60 * 60_000),
        },
        sources: [
          { sourceId: "radar", label: "Radar", status: "unavailable", detail: "Setup has not started.", lastSeenAt: null },
          { sourceId: "thermal", label: "Thermal", status: "unavailable", detail: "Setup has not started.", lastSeenAt: null },
          { sourceId: "wifi", label: "Wi-Fi sensing", status: "unavailable", detail: "Setup has not started.", lastSeenAt: null },
        ],
      },
    ],
  };
}
