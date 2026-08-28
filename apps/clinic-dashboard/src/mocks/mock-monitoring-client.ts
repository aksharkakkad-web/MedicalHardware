import type {
  EventAction,
  EventFeedbackInput,
  MonitoringClient,
  MonitoringEventDetail,
  ResidentOverviewResponse,
} from "@/lib/monitoring";
import { createEventDetailFixtures } from "./events";
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
    const historyAction: Record<EventAction, "acknowledged" | "checked"> = {
      acknowledge: "acknowledged",
      check: "checked",
    };

    if (event.status !== expectedStatus[action]) {
      throw new Error("This event action is not available in its current state.");
    }

    const status = nextStatus[action];
    const updated: MonitoringEventDetail = {
      ...event,
      status,
      overdue: action === "acknowledge" ? false : event.overdue,
      actionHistory: [
        ...event.actionHistory,
        {
          action: historyAction[action],
          actorLabel: "Demo caregiver",
          occurredAt: this.now().toISOString(),
          status,
          resolutionOutcome: null,
        },
      ],
    };
    this.events.set(eventId, updated);
    return structuredClone(updated);
  }

  async resolveEventWithFeedback(
    eventId: string,
    feedback: EventFeedbackInput,
  ): Promise<MonitoringEventDetail> {
    const event = this.getStoredEvent(eventId);
    const actualEventLabel = feedback.actualEventLabel.trim();

    if (event.status !== "checked") {
      throw new Error("This event must be checked before it can be resolved.");
    }
    if (!actualEventLabel) {
      throw new Error("Feedback must describe what happened.");
    }

    const updated: MonitoringEventDetail = {
      ...event,
      status: "resolved",
      actionHistory: [
        ...event.actionHistory,
        {
          action: "resolved",
          actorLabel: "Demo caregiver",
          occurredAt: this.now().toISOString(),
          status: "resolved",
          resolutionOutcome: feedback.outcome,
        },
      ],
      resolutionOutcome: feedback.outcome,
      feedback: {
        actualEventLabel,
        routine: feedback.routine,
        createdAt: this.now().toISOString(),
        submittedBy: "Demo caregiver",
      },
    };
    this.events.set(eventId, updated);
    return structuredClone(updated);
  }

  private getStoredEvent(eventId: string): MonitoringEventDetail {
    const stored = this.events.get(eventId);
    if (stored) {
      return stored;
    }

    const fixtures = createEventDetailFixtures(this.now());
    fixtures.forEach((fixture) => this.events.set(fixture.eventId, fixture));
    const fixture = this.events.get(eventId);
    if (!fixture) {
      throw new Error("The requested event could not be found.");
    }
    return fixture;
  }
}
