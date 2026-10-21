import type { MonitoringClient } from "@/lib/monitoring";
import type {
  AddContextInput,
  AddFollowUpInput,
  CheckRecord,
  ContextRecord,
  Facility,
  FollowUp,
  NotificationTestResult,
  RecordCheckInput,
  ResidentProfile,
  ResolveConcernInput,
  RosterImportPreview,
  RosterColumnMapping,
  SaveResidentInput,
  SharedClient,
  WorkspaceSnapshot,
  CareArea,
  WorkspacePermission,
} from "./types";
export interface WorkspaceClient {
  readonly monitoringClient: MonitoringClient;
  snapshot(): Promise<WorkspaceSnapshot>;
  subscribe(listener: () => void): () => void;
  setCurrentArea(areaId: string): Promise<void>;
  enterAdminSimulation(): Promise<void>;
  leaveAdminSimulation(): Promise<void>;
  updateFacility(input: Omit<Facility, "facilityId">): Promise<Facility>;
  saveArea(input: { areaId?: string; name: string }): Promise<CareArea>;
  approveClient(input: {
    name: string;
    areaIds: string[];
    permissions?: WorkspacePermission[];
  }): Promise<SharedClient>;
  updateClient(input: {
    clientId: string;
    name: string;
    areaIds: string[];
    permissions?: WorkspacePermission[];
    expectedConfigurationVersion?: number;
  }): Promise<SharedClient>;
  revokeClient(clientId: string): Promise<void>;
  /** Demo-only station selection; never represents real device enrollment. */
  selectDemoClient(clientId: string): Promise<void>;
  saveResident(input: SaveResidentInput): Promise<ResidentProfile>;
  acknowledgeEvent(eventId: string, requestId?: string): Promise<void>;
  recordCheck(eventId: string, input: RecordCheckInput): Promise<CheckRecord>;
  resolveEvent(eventId: string, input: ResolveConcernInput): Promise<void>;
  addContext(
    residentId: string,
    input: AddContextInput,
  ): Promise<ContextRecord>;
  addFollowUp(input: AddFollowUpInput): Promise<FollowUp>;
  completeFollowUp(followUpId: string, note?: string): Promise<void>;
  handOverFollowUp(followUpId: string, note: string): Promise<void>;
  previewRosterCsv(
    csv: string,
    fileName?: string,
    mapping?: RosterColumnMapping,
  ): Promise<RosterImportPreview>;
  applyRosterImport(importId: string): Promise<RosterImportPreview>;
  testNotifications(clientId?: string): Promise<NotificationTestResult>;
}
