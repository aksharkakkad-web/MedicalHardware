import type {
  ClinicDeviceDetailResponse,
  ClinicDeviceListResponse,
  AddMemoryEntryInput,
  CorrectMemoryEntryInput,
  EventAction,
  EventFeedbackInput,
  MonitoringEventDetail,
  MonitoringEventListResponse,
  ResidentDetailResponse,
  ResidentMonitoringSetupResponse,
  ResidentMemoryResponse,
  ResidentNotificationPreferencesResponse,
  ResidentOverviewResponse,
  SetupChangeInput,
  RetireMemoryEntryInput,
  UpdateNotificationPreferencesInput,
} from "./types";

export interface MonitoringClient {
  listDevices(): Promise<ClinicDeviceListResponse>;
  getDevice(deviceId: string): Promise<ClinicDeviceDetailResponse>;
  listResidentOverview(): Promise<ResidentOverviewResponse>;
  listEvents(): Promise<MonitoringEventListResponse>;
  getResident(residentId: string): Promise<ResidentDetailResponse>;
  getResidentMonitoringSetup(
    residentId: string,
  ): Promise<ResidentMonitoringSetupResponse>;
  recordSetupChange(
    residentId: string,
    input: SetupChangeInput,
  ): Promise<ResidentMonitoringSetupResponse>;
  getNotificationPreferences(
    residentId: string,
  ): Promise<ResidentNotificationPreferencesResponse>;
  updateNotificationPreferences(
    residentId: string,
    input: UpdateNotificationPreferencesInput,
  ): Promise<ResidentNotificationPreferencesResponse>;
  getResidentMemory(residentId: string): Promise<ResidentMemoryResponse>;
  addMemoryEntry(
    residentId: string,
    input: AddMemoryEntryInput,
  ): Promise<ResidentMemoryResponse>;
  correctMemoryEntry(
    residentId: string,
    entryId: string,
    input: CorrectMemoryEntryInput,
  ): Promise<ResidentMemoryResponse>;
  retireMemoryEntry(
    residentId: string,
    entryId: string,
    input: RetireMemoryEntryInput,
  ): Promise<ResidentMemoryResponse>;
  getEvent(eventId: string): Promise<MonitoringEventDetail>;
  performEventAction(
    eventId: string,
    action: EventAction,
  ): Promise<MonitoringEventDetail>;
  resolveEventWithFeedback(
    eventId: string,
    feedback: EventFeedbackInput,
  ): Promise<MonitoringEventDetail>;
}
