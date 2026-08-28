import type {
  ClinicDeviceDetailResponse,
  ClinicDeviceListResponse,
  EventAction,
  EventFeedbackInput,
  MonitoringClient,
  MonitoringEventDetail,
  MonitoringEventListResponse,
  ResidentDetailResponse,
  ResidentOverviewResponse,
} from "@/lib/monitoring";
import { createDeviceListFixture } from "./devices";
import { createEventDetailFixtures } from "./events";
import { createResidentOverviewFixture } from "./residents";

export interface MonitoringEventStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const STORAGE_KEY = "adaptive-care:clinic-events:v1";

function isStoredEvent(candidate: unknown): candidate is MonitoringEventDetail {
  if (typeof candidate !== "object" || candidate === null) {
    return false;
  }

  const event = candidate as Partial<MonitoringEventDetail>;
  return (
    event.schemaVersion === "1.0" &&
    typeof event.eventId === "string" &&
    typeof event.status === "string" &&
    typeof event.headline === "string" &&
    typeof event.resident === "object" &&
    event.resident !== null &&
    typeof event.confidence === "object" &&
    event.confidence !== null &&
    typeof event.interpretation === "object" &&
    event.interpretation !== null &&
    typeof event.device === "object" &&
    event.device !== null &&
    Array.isArray(event.evidence) &&
    Array.isArray(event.actionHistory) &&
    Array.isArray(event.relatedEventIds)
  );
}

export class MockMonitoringClient implements MonitoringClient {
  private readonly events = new Map<string, MonitoringEventDetail>();
  private eventsLoaded = false;

  constructor(
    private readonly now: () => Date = () => new Date(),
    private readonly storage?: MonitoringEventStorage,
  ) {}

  async listDevices(): Promise<ClinicDeviceListResponse> {
    return structuredClone(createDeviceListFixture(this.now()));
  }

  async getDevice(deviceId: string): Promise<ClinicDeviceDetailResponse> {
    const devices = await this.listDevices();
    const device = devices.items.find((item) => item.deviceId === deviceId);
    if (!device) {
      throw new Error("The requested device could not be found.");
    }
    return structuredClone({
      schemaVersion: "1.0",
      generatedAt: this.now().toISOString(),
      device,
    });
  }

  async listResidentOverview(): Promise<ResidentOverviewResponse> {
    const response = createResidentOverviewFixture(this.now());

    response.items = response.items.map((resident) => {
      const eventId = resident.attention.primaryEventId;
      if (!eventId) {
        return resident;
      }

      const event = this.getStoredEvent(eventId);
      if (event.status === "resolved") {
        return {
          ...resident,
          monitoring: {
            ...resident.monitoring,
            reason: "The event is resolved. Monitoring continues and the event history remains available.",
          },
          attention: {
            ...resident.attention,
            priority: "none",
            headline: "Event resolved — history available",
            openEventCount: 0,
          },
        };
      }

      if (event.status === "checked") {
        return {
          ...resident,
          attention: {
            ...resident.attention,
            headline: "Resident checked; resolution feedback needed",
          },
        };
      }

      if (event.status === "acknowledged") {
        return {
          ...resident,
          attention: {
            ...resident.attention,
            headline: "Event acknowledged; resident check needed",
          },
        };
      }

      return resident;
    });

    return structuredClone(response);
  }

  async listEvents(): Promise<MonitoringEventListResponse> {
    this.loadEvents();
    return structuredClone({
      schemaVersion: "1.0",
      generatedAt: this.now().toISOString(),
      items: [...this.events.values()].sort(
        (left, right) =>
          new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime(),
      ),
    });
  }

  async getResident(residentId: string): Promise<ResidentDetailResponse> {
    const overview = await this.listResidentOverview();
    const resident = overview.items.find((item) => item.residentId === residentId);
    if (!resident) {
      throw new Error("The requested resident could not be found.");
    }
    const eventResponse = await this.listEvents();
    return structuredClone({
      schemaVersion: "1.0",
      generatedAt: this.now().toISOString(),
      resident,
      events: eventResponse.items.filter(
        (event) => event.resident.residentId === residentId,
      ),
    });
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
    this.persistEvents();
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
    this.persistEvents();
    return structuredClone(updated);
  }

  private getStoredEvent(eventId: string): MonitoringEventDetail {
    this.loadEvents();
    const stored = this.events.get(eventId);
    if (stored) {
      return stored;
    }

    throw new Error("The requested event could not be found.");
  }

  private loadEvents(): void {
    if (this.eventsLoaded) {
      return;
    }
    this.eventsLoaded = true;

    createEventDetailFixtures(this.now()).forEach((fixture) => {
      this.events.set(fixture.eventId, fixture);
    });

    try {
      const saved = this.storage?.getItem(STORAGE_KEY);
      if (!saved) {
        return;
      }

      const parsed: unknown = JSON.parse(saved);
      if (!Array.isArray(parsed)) {
        return;
      }

      parsed.forEach((candidate) => {
        if (isStoredEvent(candidate) && this.events.has(candidate.eventId)) {
          this.events.set(candidate.eventId, candidate);
        }
      });
    } catch {
      // Broken demo storage is ignored so the safe fixtures remain usable.
    }
  }

  private persistEvents(): void {
    try {
      this.storage?.setItem(STORAGE_KEY, JSON.stringify([...this.events.values()]));
    } catch {
      // The workflow still works for this visit if browser storage is unavailable.
    }
  }
}
