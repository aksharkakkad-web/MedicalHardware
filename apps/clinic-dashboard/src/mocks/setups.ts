import type { ResidentMonitoringSetup } from "@/lib/monitoring";

function before(now: Date, minutes: number): string {
  return new Date(now.getTime() - minutes * 60_000).toISOString();
}

function establishedDimensions(): ResidentMonitoringSetup["dimensions"] {
  return [
    { schemaVersion: "1.0", dimension: "movement", status: "established", eligibleWindows: 12, excludedWindows: 2 },
    { schemaVersion: "1.0", dimension: "respiratory_rate", status: "established", eligibleWindows: 12, excludedWindows: 2 },
  ];
}

export function createMonitoringSetupFixtures(now: Date): ResidentMonitoringSetup[] {
  const base = (residentId: string, residentLabel: string, roomId: string, roomLabel: string, deviceId: string, deviceLabel: string): ResidentMonitoringSetup => ({
    schemaVersion: "1.0",
    residentId,
    residentLabel,
    roomId,
    roomLabel,
    deviceId,
    deviceLabel,
    deviceStatus: "online",
    assignmentStatus: "valid",
    setupVersion: `setup_${roomId}_v1`,
    version: 1,
    recordedAt: before(now, 60),
    status: "established",
    reason: "Calibration is established for this room setup.",
    learningState: "active",
    learningReason: "The demo can collect clean resident-specific calibration data.",
    priorSetupVersions: [],
    dimensions: establishedDimensions(),
    setupChanges: [],
  });

  const items = [
    base("res_7f3a1c", "Resident A", "room_b14e2d", "Room 101", "dev_room_101", "Northstar 101"),
    base("res_2c8d4f", "Resident B", "room_6a91c3", "Room 102", "dev_room_102", "Northstar 102"),
    base("res_91be60", "Resident C", "room_3d72ab", "Room 103", "dev_room_103", "Northstar 103"),
    base("res_4ab783", "Resident D", "room_85cd20", "Room 104", "dev_room_104", "Northstar 104"),
    base("res_d0e519", "Resident E", "room_1f64b8", "Room 105", "dev_room_105", "Northstar 105"),
  ];

  items[1] = {
    ...items[1],
    recordedAt: before(now, 18),
    status: "calibrating",
    reason: "A new room setup is collecting enough clean demo data to establish a baseline.",
    dimensions: items[1].dimensions.map((dimension) => ({ ...dimension, status: "calibrating", eligibleWindows: 4, excludedWindows: 1 })),
  };
  items[2] = {
    ...items[2],
    learningState: "paused",
    learningReason: "New learning is paused while the resident is away. Established calibration history is preserved.",
  };
  items[3] = {
    ...items[3],
    learningState: "paused",
    learningReason: "New learning is paused until room occupancy is clear. Established calibration history is preserved.",
  };
  items[4] = {
    ...items[4],
    deviceStatus: "offline",
    learningState: "unavailable",
    learningReason: "The room device is offline, so no new calibration data can be collected. Established history is preserved.",
  };

  return [
    ...items,
    {
      schemaVersion: "1.0",
      residentId: "res_assignment_review",
      residentLabel: "Resident F",
      roomId: null,
      roomLabel: null,
      deviceId: null,
      deviceLabel: null,
      deviceStatus: "unknown",
      assignmentStatus: "conflicting",
      setupVersion: null,
      version: 0,
      recordedAt: before(now, 5),
      status: "new",
      reason: "Two room records point to this resident. An authorized administrator must resolve the assignment before setup can begin.",
      learningState: "unavailable",
      learningReason: "Learning cannot begin until an authorized administrator resolves the assignment.",
      priorSetupVersions: [],
      dimensions: [
        { schemaVersion: "1.0", dimension: "movement", status: "new", eligibleWindows: 0, excludedWindows: 0 },
        { schemaVersion: "1.0", dimension: "respiratory_rate", status: "new", eligibleWindows: 0, excludedWindows: 0 },
      ],
      setupChanges: [],
    },
  ];
}
