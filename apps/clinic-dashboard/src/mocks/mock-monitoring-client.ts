import type {
  EventAction,
  MonitoringClient,
  MonitoringEventDetail,
  ResidentOverviewResponse,
} from "@/lib/monitoring";
import { createEventDetailFixture } from "./events";
import { createResidentOverviewFixture } from "./residents";

export class MockMonitoringClient implements MonitoringClient {
  private readonly events = new Map<string, MonitoringEventDetail>();

  constructor(private readonly now: () => Date = () => new Date()) {}

  async listResidentOverview(): Promise<ResidentOverviewResponse> {
    return structuredClone(createResidentOverviewFixture(this.now()));
  }

  async getEvent(eventId: string): Promise<MonitoringEventDetail> {
    const event = this.getStoredEvent(eventId);
    return structuredClone(event);
  }

  async performEventAction(
    eventId: string,
    action: EventAction,
  ): Promise<MonitoringEventDetail> {
    const event = this.getStoredEvent(eventId);
    const expectedStatus: Record<EventAction, MonitoringEventDetail["status"]> = {
      acknowledge: "open",
      check: "acknowledged",
    };
    const nextStatus: Record<EventAction, MonitoringEventDetail["status"]> = {
      acknowledge: "acknowledged",
      check: "checked",
    };

    if (event.status !== expectedStatus[action]) {
      throw new Error("This event action is not available in its current state.");
    }

    const updated = { ...event, status: nextStatus[action] };
    this.events.set(eventId, updated);
    return structuredClone(updated);
  }

  private getStoredEvent(eventId: string): MonitoringEventDetail {
    const stored = this.events.get(eventId);
    if (stored) {
      return stored;
    }

    const fixture = createEventDetailFixture(this.now());
    if (fixture.eventId !== eventId) {
      throw new Error("The requested event could not be found.");
    }

    this.events.set(eventId, fixture);
    return fixture;
  }
}
