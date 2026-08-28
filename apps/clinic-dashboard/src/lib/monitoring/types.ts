export type MonitoringState =
  | "active"
  | "limited"
  | "paused"
  | "unavailable";

export type AttentionPriority = "none" | "watch" | "high" | "critical";

export type DeviceStatus = "online" | "degraded" | "offline" | "unknown";

export type ClinicDeviceStatus =
  | "online"
  | "degraded"
  | "offline"
  | "buffering"
  | "retrying"
  | "unavailable";

export type DataAvailability =
  | "available"
  | "limited"
  | "unavailable"
  | "not_yet_available";

export interface ClinicDevice {
  schemaVersion: "1.0";
  deviceId: string;
  displayLabel: string;
  modelLabel: string;
  roomId: string | null;
  roomLabel: string | null;
  residentId: string | null;
  residentLabel: string | null;
  assignmentStatus: "assigned" | "unassigned" | "conflicting";
  health: {
    status: ClinicDeviceStatus;
    dataAvailability: DataAvailability;
    summary: string;
    lastSeenAt: string | null;
  };
  setup: {
    version: number;
    state: "ready" | "calibrating" | "needs_attention" | "not_started";
    updatedAt: string;
  };
  sources: Array<{
    sourceId: "radar" | "thermal" | "wifi";
    label: string;
    status: "available" | "limited" | "unavailable";
    detail: string;
    lastSeenAt: string | null;
  }>;
}

export interface ClinicDeviceListResponse {
  schemaVersion: "1.0";
  generatedAt: string;
  items: ClinicDevice[];
}

export interface ClinicDeviceDetailResponse {
  schemaVersion: "1.0";
  generatedAt: string;
  device: ClinicDevice;
}

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

export type EventHistoryAction =
  | "opened"
  | "acknowledged"
  | "checked"
  | "resolved";

export interface EventHistoryItem {
  action: EventHistoryAction;
  actorLabel: string;
  occurredAt: string;
  status: EventStatus;
  resolutionOutcome: ResolutionOutcome | null;
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

export interface MonitoringEventListResponse {
  schemaVersion: "1.0";
  generatedAt: string;
  items: MonitoringEventDetail[];
}

export interface ResidentDetailResponse {
  schemaVersion: "1.0";
  generatedAt: string;
  resident: ResidentOverviewItem;
  events: MonitoringEventDetail[];
}

export type CalibrationStatus =
  | "new"
  | "calibrating"
  | "partial"
  | "established";

export type CalibrationDimensionId = "movement" | "respiratory_rate";

export type CalibrationDimensionStatus =
  | "new"
  | "calibrating"
  | "partial"
  | "established";

export type SetupChangeReason =
  | "device_moved"
  | "room_layout_changed"
  | "core_sensor_replaced"
  | "resident_moved";

export interface SetupChangeInput {
  reason: SetupChangeReason;
  affectedDimensions: CalibrationDimensionId[];
  expectedCalibrationVersion: number;
}

export interface ResidentMonitoringSetup {
  schemaVersion: "1.0";
  residentId: string;
  residentLabel: string;
  roomId: string | null;
  roomLabel: string | null;
  deviceId: string | null;
  deviceLabel: string | null;
  deviceStatus: DeviceStatus;
  assignmentStatus: "valid" | "missing" | "conflicting";
  setupVersion: string | null;
  version: number;
  recordedAt: string;
  status: CalibrationStatus;
  reason: string;
  learningState: "active" | "paused" | "unavailable";
  learningReason: string;
  priorSetupVersions: string[];
  dimensions: Array<{
    schemaVersion: "1.0";
    dimension: CalibrationDimensionId;
    status: CalibrationDimensionStatus;
    eligibleWindows: number;
    excludedWindows: number;
  }>;
  setupChanges: Array<{
    schemaVersion: "1.0";
    previousSetupVersion: string;
    newSetupVersion: string;
    affectedDimensions: CalibrationDimensionId[];
    reason: SetupChangeReason;
    actorLabel: string;
    changedAt: string;
  }>;
}

export interface ResidentMonitoringSetupResponse {
  schemaVersion: "1.0";
  generatedAt: string;
  setup: ResidentMonitoringSetup;
}

export interface NotificationDeliveryChoices {
  watch: boolean;
  high: boolean;
  critical: boolean;
}

export interface AwarenessDeliveryChoices {
  away: boolean;
  return: boolean;
  limited: boolean;
  unavailable: boolean;
}

export interface ResidentNotificationPreferencesResponse {
  schemaVersion: "1.0";
  residentId: string;
  dataAvailability: "available" | "not_yet_available";
  version: number | null;
  eventDelivery: NotificationDeliveryChoices | null;
  awarenessDelivery: AwarenessDeliveryChoices | null;
  highCriticalDashboardVisibility: "always_visible";
  changedBy: string | null;
  changedAt: string | null;
}

export interface UpdateNotificationPreferencesInput {
  expectedVersion: number;
  eventDelivery: NotificationDeliveryChoices;
  awarenessDelivery: AwarenessDeliveryChoices;
}

export interface ResidentMemoryEntry {
  schemaVersion: "1.0";
  entryId: string;
  description: string;
  sourceKind: "feedback" | "operator";
  sourceFeedbackId: string | null;
  supersedesEntryId: string | null;
  status: "active" | "retired";
  createdBy: string;
  createdAt: string;
  retiredBy: string | null;
  retiredAt: string | null;
  retirementReason: string | null;
}

export interface ResidentMemoryResponse {
  schemaVersion: "1.0";
  residentId: string;
  version: number;
  entries: ResidentMemoryEntry[];
}

export interface AddMemoryEntryInput {
  expectedVersion: number;
  description: string;
}

export interface CorrectMemoryEntryInput extends AddMemoryEntryInput {
  reason: string;
}

export interface RetireMemoryEntryInput {
  expectedVersion: number;
  reason: string;
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
  overdue: boolean;
  overdueAt: string | null;
  actionHistory: EventHistoryItem[];
  resolutionOutcome: ResolutionOutcome | null;
  feedback: {
    actualEventLabel: string;
    routine: boolean;
    createdAt: string;
    submittedBy: string;
  } | null;
}
