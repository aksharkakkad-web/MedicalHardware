import type {
  EventAction,
  EventFeedbackInput,
  MonitoringEventDetail,
  MonitoringEventListResponse,
  ResidentDetailResponse,
  ResidentOverviewResponse,
} from "./types";

export interface MonitoringClient {
  listResidentOverview(): Promise<ResidentOverviewResponse>;
  listEvents(): Promise<MonitoringEventListResponse>;
  getResident(residentId: string): Promise<ResidentDetailResponse>;
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
