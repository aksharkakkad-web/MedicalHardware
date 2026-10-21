import type {
  EventFeedbackInput,
  MonitoringEventDetail,
  ResidentOverviewItem,
} from "@/lib/monitoring";
/** Frontend demo view models; these are not a production backend/auth contract. */
export interface Facility {
  facilityId: string;
  name: string;
  timeZone: string;
  coverageContact: string;
  escalationContact: string;
}
export interface CareArea {
  areaId: string;
  name: string;
  roomIds: string[];
}
export type WorkspacePermission =
  | "acknowledge"
  | "record_check"
  | "resolve_concern"
  | "add_follow_up"
  | "update_follow_up"
  | "report_context";
export interface SharedClient {
  clientId: string;
  name: string;
  areaIds: string[];
  permissions: WorkspacePermission[];
  configurationVersion: number;
  status: "approved" | "revoked";
  approvedAt: string;
  notificationStatus: "not_configured" | "blocked";
}
export interface ResidentProfile {
  residentId: string;
  name: string;
  facilityResidentId: string;
  areaId: string;
  roomId: string;
  roomLabel: string;
  admittedAt: string;
  departedAt: string | null;
  assignmentEffectiveAt: string;
  synthetic: true;
}
export interface ResidentMeasurement {
  residentId: string;
  kind: "pulse" | "breathing";
  label: string;
  value: number | null;
  unit: string;
  observedAt: string | null;
  quality: "demo" | "unavailable";
  attribution: "eligible" | "unavailable";
  reason: string;
  synthetic: true;
}
export interface ContextRecord {
  contextId: string;
  residentId: string;
  category:
    "preference" | "care_goal" | "hospice" | "observation" | "correction";
  text: string;
  source: string;
  recordedAt: string;
  effectiveUntil: string | null;
  reviewStatus: "demo_reviewed" | "needs_review";
  supersedesContextId: string | null;
}
export type CheckOutcome =
  | "no_concern_observed"
  | "concern_remains"
  | "assistance_requested"
  | "unable_to_check"
  | "information_needs_review"
  | "other";
export interface CheckRecord {
  checkId: string;
  eventId: string;
  residentId: string;
  outcome: CheckOutcome;
  note: string;
  checkedAt: string;
  recordedAt: string;
  clientId: string;
  clientLabel: string;
  completedCheck: boolean;
  requestId: string;
}
export interface FollowUpHistoryItem {
  action: "handed_over" | "completed";
  note: string | null;
  recordedAt: string;
  clientLabel: string;
}
export interface FollowUp {
  followUpId: string;
  residentId: string;
  eventId: string | null;
  text: string;
  createdAt: string;
  dueAt: string | null;
  status: "open" | "completed" | "handed_over";
  completionNote: string | null;
  history?: FollowUpHistoryItem[];
  completedAt: string | null;
  clientLabel: string;
}
export interface AssignmentHistory {
  residentId: string;
  fromRoomId: string | null;
  toRoomId: string;
  effectiveAt: string;
  recordedAt: string;
}
export interface RosterImportRow {
  rowNumber: number;
  facilityResidentId: string;
  name: string;
  roomLabel: string;
  areaName: string;
  issues: string[];
  action: "add" | "update" | "blocked";
  residentId: string | null;
}
export interface RosterImportPreview {
  importId: string;
  fileName: string;
  createdAt: string;
  expectedVersion: number;
  rows: RosterImportRow[];
  canApply: boolean;
  status: "ready_for_review" | "rejected" | "applied";
  appliedAt: string | null;
  synthetic: true;
}
export type RosterColumnMapping = Partial<
  Record<"facilityResidentId" | "name" | "roomLabel" | "areaName", string>
>;
export interface NotificationTestResult {
  status: "blocked";
  testedAt: string;
  clientId: string;
  delivered: false;
  reason: string;
}
export interface WorkspaceSnapshot {
  mode: "demo";
  demoNotice: string;
  sourceObservedAt: string;
  synchronizedAt: string;
  version: number;
  facility: Facility;
  areas: CareArea[];
  currentClient: SharedClient;
  clients: SharedClient[];
  currentAreaId: string;
  admin: {
    active: boolean;
    simulated: true;
  };
  residents: ResidentOverviewItem[];
  events: MonitoringEventDetail[];
  profiles: ResidentProfile[];
  measurements: ResidentMeasurement[];
  contexts: ContextRecord[];
  checks: CheckRecord[];
  followUps: FollowUp[];
  imports: RosterImportPreview[];
  assignmentHistory: AssignmentHistory[];
  persistence: {
    available: boolean;
    message: string;
  };
  capabilities: {
    authentication: false;
    serverSync: false;
    documentExtraction: false;
    xlsxImport: false;
    backgroundNotifications: false;
  };
}
export interface RecordCheckInput {
  outcome: CheckOutcome;
  note?: string;
  checkedAt?: string;
  requestId?: string;
}
export interface SaveResidentInput {
  residentId?: string;
  name: string;
  facilityResidentId: string;
  areaId: string;
  roomLabel: string;
  effectiveAt?: string;
  admittedAt?: string;
  departedAt?: string | null;
}
export interface AddContextInput {
  text: string;
  category?: ContextRecord["category"];
  source?: string;
  effectiveUntil?: string | null;
  supersedesContextId?: string;
}
export interface AddFollowUpInput {
  residentId: string;
  eventId?: string;
  text: string;
  dueAt?: string;
}
export interface ResolveConcernInput extends EventFeedbackInput {
  requestId?: string;
}
