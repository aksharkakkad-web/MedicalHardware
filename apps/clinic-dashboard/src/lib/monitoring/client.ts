import type {
  EventAction,
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
}
