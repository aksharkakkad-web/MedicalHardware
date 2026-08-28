export type MonitoringState =
  | "active"
  | "limited"
  | "paused"
  | "unavailable";

export type AttentionPriority = "none" | "watch" | "high" | "critical";

export type DeviceStatus = "online" | "degraded" | "offline" | "unknown";

export type EventStatus =
  | "detected"
  | "open"
  | "acknowledged"
  | "checked"
  | "resolved";

export type EventAction = "acknowledge" | "check";

export type InterpretationStatus = "pending" | "complete" | "unavailable";

export type ResolutionOutcome = "confirmed" | "false_positive" | "uncertain";

export interface EventFeedbackInput {
  outcome: ResolutionOutcome;
  actualEventLabel: string;
  routine: boolean;
}

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
    contextLabel?: string;
    lastUpdatedAt: string;
  };
  attention: {
    priority: AttentionPriority;
    headline: string;
    openEventCount: number;
    primaryEventId?: string;
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

export interface MonitoringEventDetail {
  schemaVersion: "1.0";
  eventId: string;
  resident: {
    residentId: string;
    displayLabel: string;
    roomId: string;
    roomLabel: string;
  };
  createdAt: string;
  lastSignalAt: string;
  status: EventStatus;
  priority: Exclude<AttentionPriority, "none">;
  headline: string;
  objectiveFamily: string;
  confidence: {
    value: number;
    label: string;
    dataQuality: "good" | "limited" | "unavailable";
    limitation: string | null;
  };
  evidence: Array<{
    evidenceId: string;
    label: string;
    observation: string;
    recordedAt: string;
    quality: "good" | "limited" | "unavailable";
  }>;
  interpretation: {
    status: InterpretationStatus;
    summary: string | null;
    uncertainty: string;
  };
  device: {
    status: DeviceStatus;
    label: string;
    sources: Array<{
      label: string;
      status: "available" | "limited" | "unavailable";
    }>;
  };
  relatedEventIds: string[];
  recurrenceCount: number;
  resolutionOutcome: ResolutionOutcome | null;
  feedback: {
    actualEventLabel: string;
    routine: boolean;
    createdAt: string;
  } | null;
}
