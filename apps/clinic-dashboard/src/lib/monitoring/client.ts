import type {
  ClinicDeviceDetailResponse,
  ClinicDeviceListResponse,
  EventAction,
  EventFeedbackInput,
  MonitoringEventDetail,
  MonitoringEventListResponse,
  ResidentDetailResponse,
  ResidentMonitoringSetupResponse,
  ResidentOverviewResponse,
  SetupChangeInput,
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
