import type {
  EventAction,
  EventFeedbackInput,
  MonitoringEventDetail,
  ResidentOverviewResponse,
} from "./types";

export interface MonitoringClient {
  listResidentOverview(): Promise<ResidentOverviewResponse>;
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
