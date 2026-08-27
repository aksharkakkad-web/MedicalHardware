export type MonitoringState =
  | "active"
  | "limited"
  | "paused"
  | "unavailable";

export type AttentionPriority = "none" | "watch" | "high" | "critical";

export type DeviceStatus = "online" | "degraded" | "offline" | "unknown";

export interface ResidentOverviewItem {
  schemaVersion: "1.0";
  residentId: string;
  displayLabel: string;
  roomId: string;
  roomLabel: string;
  assignmentStatus: "active" | "missing" | "conflicting";
  monitoring: {
    state: MonitoringState;
    reason: string;
    lastUpdatedAt: string;
  };
  attention: {
    priority: AttentionPriority;
    headline: string;
    openEventCount: number;
  };
  device: {
    status: DeviceStatus;
    label: string;
  };
}

export interface ResidentOverviewResponse {
  schemaVersion: "1.0";
  generatedAt: string;
  items: ResidentOverviewItem[];
}
