import type {
  AddMemoryEntryInput,
  ClinicDeviceDetailResponse,
  ClinicDeviceListResponse,
  CorrectMemoryEntryInput,
  EventAction,
  EventFeedbackInput,
  MonitoringClient,
  MonitoringEventDetail,
  MonitoringEventListResponse,
  ResidentDetailResponse,
  ResidentMonitoringSetup,
  ResidentMonitoringSetupResponse,
  ResidentMemoryEntry,
  ResidentMemoryResponse,
  ResidentNotificationPreferencesResponse,
  ResidentOverviewResponse,
  RetireMemoryEntryInput,
  SetupChangeInput,
  UpdateNotificationPreferencesInput,
} from "@/lib/monitoring";
import { createDeviceListFixture } from "./devices";
import { createEventDetailFixtures } from "./events";
import { createResidentOverviewFixture } from "./residents";
import { createMemoryFixtures, createPreferenceFixtures } from "./resident-settings";
import { createMonitoringSetupFixtures } from "./setups";

export interface MonitoringStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const EVENT_STORAGE_KEY = "adaptive-care:clinic-events:v1";
const SETUP_STORAGE_KEY = "adaptive-care:clinic-setups:v2";
const PREFERENCE_STORAGE_KEY = "adaptive-care:clinic-preferences:v1";
const MEMORY_STORAGE_KEY = "adaptive-care:resident-memory:v1";

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

function isStoredSetup(candidate: unknown): candidate is ResidentMonitoringSetup {
  if (typeof candidate !== "object" || candidate === null) return false;
  const setup = candidate as Partial<ResidentMonitoringSetup>;
  const allowedStatuses = new Set(["new", "calibrating", "partial", "established"]);
  return setup.schemaVersion === "1.0" && typeof setup.residentId === "string" && typeof setup.version === "number" && typeof setup.learningState === "string" && typeof setup.learningReason === "string" && typeof setup.status === "string" && allowedStatuses.has(setup.status) && Array.isArray(setup.dimensions) && setup.dimensions.every((dimension) => allowedStatuses.has(dimension.status)) && Array.isArray(setup.setupChanges);
}

function isStoredPreference(candidate: unknown): candidate is ResidentNotificationPreferencesResponse {
  if (typeof candidate !== "object" || candidate === null) return false;
  const preference = candidate as Partial<ResidentNotificationPreferencesResponse>;
  return preference.schemaVersion === "1.0" && typeof preference.residentId === "string" && (preference.dataAvailability === "available" || preference.dataAvailability === "not_yet_available") && preference.highCriticalDashboardVisibility === "always_visible";
}

function isStoredMemory(candidate: unknown): candidate is ResidentMemoryResponse {
  if (typeof candidate !== "object" || candidate === null) return false;
  const memory = candidate as Partial<ResidentMemoryResponse>;
  return memory.schemaVersion === "1.0" && typeof memory.residentId === "string" && typeof memory.version === "number" && Array.isArray(memory.entries);
}

export class MockMonitoringClient implements MonitoringClient {
  private readonly events = new Map<string, MonitoringEventDetail>();
  private readonly setups = new Map<string, ResidentMonitoringSetup>();
  private readonly preferences = new Map<string, ResidentNotificationPreferencesResponse>();
  private readonly memories = new Map<string, ResidentMemoryResponse>();
  private eventsLoaded = false;
  private setupsLoaded = false;
  private preferencesLoaded = false;
  private memoriesLoaded = false;

  constructor(
    private readonly now: () => Date = () => new Date(),
    private readonly storage?: MonitoringStorage,
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

  async getResidentMonitoringSetup(
    residentId: string,
  ): Promise<ResidentMonitoringSetupResponse> {
    const setup = this.getStoredSetup(residentId);
    return structuredClone({
      schemaVersion: "1.0",
      generatedAt: this.now().toISOString(),
      setup,
    });
  }

  async recordSetupChange(
    residentId: string,
    input: SetupChangeInput,
  ): Promise<ResidentMonitoringSetupResponse> {
    const setup = this.getStoredSetup(residentId);
    if (setup.assignmentStatus !== "valid") {
      throw new Error("Resolve the room assignment before recording a setup change.");
    }
    if (input.affectedDimensions.length === 0) {
      throw new Error("Choose at least one calibration area.");
    }
    if (input.expectedCalibrationVersion !== setup.version) {
      throw new Error("This setup changed in another session. Refresh before trying again.");
    }

    const changedAt = this.now().toISOString();
    const previousSetupVersion = setup.setupVersion ?? `setup_${setup.roomId ?? "unassigned"}_v${setup.version}`;
    const version = setup.version + 1;
    const newSetupVersion = `setup_${setup.roomId}_v${version}`;
    const affected = new Set(input.affectedDimensions);
    const dimensions = setup.dimensions.map((dimension) => affected.has(dimension.dimension) ? { ...dimension, status: "calibrating" as const, eligibleWindows: 0, excludedWindows: 0 } : dimension);
    const status = dimensions.every((dimension) => dimension.status === "established")
      ? "established"
      : dimensions.some((dimension) => dimension.status === "established" || dimension.status === "partial")
        ? "partial"
        : "calibrating";
    const updated: ResidentMonitoringSetup = {
      ...setup,
      version,
      recordedAt: changedAt,
      setupVersion: newSetupVersion,
      status,
      reason: "Only the selected calibration areas restarted. Other established areas were preserved.",
      priorSetupVersions: [...setup.priorSetupVersions, previousSetupVersion],
      dimensions,
      setupChanges: [
        ...setup.setupChanges,
        {
          schemaVersion: "1.0",
          previousSetupVersion,
          newSetupVersion,
          affectedDimensions: [...input.affectedDimensions],
          reason: input.reason,
          actorLabel: "Demo caregiver",
          changedAt,
        },
      ],
    };
    this.setups.set(residentId, updated);
    this.persistSetups();
    return this.getResidentMonitoringSetup(residentId);
  }

  async getNotificationPreferences(
    residentId: string,
  ): Promise<ResidentNotificationPreferencesResponse> {
    this.loadPreferences();
    const preferences = this.preferences.get(residentId);
    if (!preferences) throw new Error("The requested notification preferences could not be found.");
    return structuredClone(preferences);
  }

  async updateNotificationPreferences(
    residentId: string,
    input: UpdateNotificationPreferencesInput,
  ): Promise<ResidentNotificationPreferencesResponse> {
    const current = await this.getNotificationPreferences(residentId);
    const actualVersion = current.version ?? 0;
    if (input.expectedVersion !== actualVersion) {
      throw new Error("These preferences changed in another session. Refresh before trying again.");
    }
    const updated: ResidentNotificationPreferencesResponse = {
      schemaVersion: "1.0",
      residentId,
      dataAvailability: "available",
      version: actualVersion + 1,
      eventDelivery: { ...input.eventDelivery },
      awarenessDelivery: { ...input.awarenessDelivery },
      highCriticalDashboardVisibility: "always_visible",
      changedBy: "Demo administrator",
      changedAt: this.now().toISOString(),
    };
    this.preferences.set(residentId, updated);
    this.persistPreferences();
    return structuredClone(updated);
  }

  async getResidentMemory(residentId: string): Promise<ResidentMemoryResponse> {
    this.loadMemories();
    const memory = this.memories.get(residentId);
    if (!memory) throw new Error("The requested resident context could not be found.");
    return structuredClone(memory);
  }

  async addMemoryEntry(
    residentId: string,
    input: AddMemoryEntryInput,
  ): Promise<ResidentMemoryResponse> {
    const current = await this.getResidentMemory(residentId);
    this.requireMemoryVersion(current, input.expectedVersion);
    const description = this.requireText(input.description, "Describe the resident context before saving.");
    const version = current.version + 1;
    const changedAt = this.now().toISOString();
    const entry: ResidentMemoryEntry = {
      schemaVersion: "1.0",
      entryId: `mem_${residentId}_${version}_${current.entries.length + 1}`,
      description,
      sourceKind: "operator",
      sourceFeedbackId: null,
      supersedesEntryId: null,
      status: "active",
      createdBy: "Demo caregiver",
      createdAt: changedAt,
      retiredBy: null,
      retiredAt: null,
      retirementReason: null,
    };
    return this.saveMemory({ ...current, version, entries: [...current.entries, entry] });
  }

  async correctMemoryEntry(
    residentId: string,
    entryId: string,
    input: CorrectMemoryEntryInput,
  ): Promise<ResidentMemoryResponse> {
    const current = await this.getResidentMemory(residentId);
    this.requireMemoryVersion(current, input.expectedVersion);
    const target = this.requireActiveMemoryEntry(current, entryId);
    const description = this.requireText(input.description, "Enter the corrected context before saving.");
    const reason = this.requireText(input.reason, "Explain why this context is being corrected.");
    const changedAt = this.now().toISOString();
    const version = current.version + 1;
    const retired = current.entries.map((entry) => entry.entryId === entryId ? { ...entry, status: "retired" as const, retiredBy: "Demo caregiver", retiredAt: changedAt, retirementReason: reason } : entry);
    const replacement: ResidentMemoryEntry = {
      ...target,
      entryId: `mem_${residentId}_${version}_${current.entries.length + 1}`,
      description,
      sourceKind: "operator",
      sourceFeedbackId: null,
      supersedesEntryId: target.entryId,
      status: "active",
      createdBy: "Demo caregiver",
      createdAt: changedAt,
      retiredBy: null,
      retiredAt: null,
      retirementReason: null,
    };
    return this.saveMemory({ ...current, version, entries: [...retired, replacement] });
  }

  async retireMemoryEntry(
    residentId: string,
    entryId: string,
    input: RetireMemoryEntryInput,
  ): Promise<ResidentMemoryResponse> {
    const current = await this.getResidentMemory(residentId);
    this.requireMemoryVersion(current, input.expectedVersion);
    this.requireActiveMemoryEntry(current, entryId);
    const reason = this.requireText(input.reason, "Explain why this context is no longer current.");
    const changedAt = this.now().toISOString();
    return this.saveMemory({
      ...current,
      version: current.version + 1,
      entries: current.entries.map((entry) => entry.entryId === entryId ? { ...entry, status: "retired" as const, retiredBy: "Demo caregiver", retiredAt: changedAt, retirementReason: reason } : entry),
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
    if (feedback.routine && actualEventLabel.toLowerCase() !== "unknown") {
      this.recordFeedbackMemory(updated, actualEventLabel);
    }
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

  private getStoredSetup(residentId: string): ResidentMonitoringSetup {
    this.loadSetups();
    const setup = this.setups.get(residentId);
    if (setup) return setup;
    throw new Error("The requested monitoring setup could not be found.");
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
      const saved = this.storage?.getItem(EVENT_STORAGE_KEY);
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
      this.storage?.setItem(EVENT_STORAGE_KEY, JSON.stringify([...this.events.values()]));
    } catch {
      // The workflow still works for this visit if browser storage is unavailable.
    }
  }

  private loadSetups(): void {
    if (this.setupsLoaded) return;
    this.setupsLoaded = true;
    createMonitoringSetupFixtures(this.now()).forEach((fixture) => this.setups.set(fixture.residentId, fixture));

    try {
      const saved = this.storage?.getItem(SETUP_STORAGE_KEY);
      if (!saved) return;
      const parsed: unknown = JSON.parse(saved);
      if (!Array.isArray(parsed)) return;
      parsed.forEach((candidate) => {
        if (isStoredSetup(candidate) && this.setups.has(candidate.residentId)) this.setups.set(candidate.residentId, candidate);
      });
    } catch {
      // Broken demo storage is ignored so the safe fixtures remain usable.
    }
  }

  private persistSetups(): void {
    try {
      this.storage?.setItem(SETUP_STORAGE_KEY, JSON.stringify([...this.setups.values()]));
    } catch {
      // The workflow still works for this visit if browser storage is unavailable.
    }
  }

  private loadPreferences(): void {
    if (this.preferencesLoaded) return;
    this.preferencesLoaded = true;
    createPreferenceFixtures(this.now()).forEach((fixture) => this.preferences.set(fixture.residentId, fixture));
    this.loadStoredCollection(PREFERENCE_STORAGE_KEY, isStoredPreference, this.preferences);
  }

  private persistPreferences(): void {
    this.persistCollection(PREFERENCE_STORAGE_KEY, this.preferences);
  }

  private loadMemories(): void {
    if (this.memoriesLoaded) return;
    this.memoriesLoaded = true;
    createMemoryFixtures(this.now()).forEach((fixture) => this.memories.set(fixture.residentId, fixture));
    this.loadStoredCollection(MEMORY_STORAGE_KEY, isStoredMemory, this.memories);
  }

  private persistMemories(): void {
    this.persistCollection(MEMORY_STORAGE_KEY, this.memories);
  }

  private loadStoredCollection<T extends { residentId: string }>(
    key: string,
    validator: (candidate: unknown) => candidate is T,
    target: Map<string, T>,
  ): void {
    try {
      const saved = this.storage?.getItem(key);
      if (!saved) return;
      const parsed: unknown = JSON.parse(saved);
      if (!Array.isArray(parsed)) return;
      parsed.forEach((candidate) => {
        if (validator(candidate) && target.has(candidate.residentId)) target.set(candidate.residentId, candidate);
      });
    } catch {
      // Broken demo storage is ignored so the safe fixtures remain usable.
    }
  }

  private persistCollection<T>(key: string, collection: Map<string, T>): void {
    try {
      this.storage?.setItem(key, JSON.stringify([...collection.values()]));
    } catch {
      // The workflow still works for this visit if browser storage is unavailable.
    }
  }

  private requireMemoryVersion(memory: ResidentMemoryResponse, expectedVersion: number): void {
    if (memory.version !== expectedVersion) {
      throw new Error("This resident context changed in another session. Refresh before trying again.");
    }
  }

  private requireActiveMemoryEntry(memory: ResidentMemoryResponse, entryId: string): ResidentMemoryEntry {
    const entry = memory.entries.find((candidate) => candidate.entryId === entryId);
    if (!entry || entry.status !== "active") throw new Error("This context entry is no longer available to change.");
    return entry;
  }

  private requireText(value: string, message: string): string {
    const normalized = value.trim();
    if (!normalized) throw new Error(message);
    return normalized;
  }

  private saveMemory(memory: ResidentMemoryResponse): ResidentMemoryResponse {
    this.memories.set(memory.residentId, memory);
    this.persistMemories();
    return structuredClone(memory);
  }

  private recordFeedbackMemory(event: MonitoringEventDetail, description: string): void {
    this.loadMemories();
    const memory = this.memories.get(event.resident.residentId);
    if (!memory) return;
    const sourceFeedbackId = `fb_${event.eventId}`;
    if (memory.entries.some((entry) => entry.sourceFeedbackId === sourceFeedbackId)) return;
    const createdAt = this.now().toISOString();
    const version = memory.version + 1;
    const entry: ResidentMemoryEntry = {
      schemaVersion: "1.0",
      entryId: `mem_${event.resident.residentId}_${version}_${memory.entries.length + 1}`,
      description,
      sourceKind: "feedback",
      sourceFeedbackId,
      supersedesEntryId: null,
      status: "active",
      createdBy: "Demo caregiver",
      createdAt,
      retiredBy: null,
      retiredAt: null,
      retirementReason: null,
    };
    this.memories.set(memory.residentId, { ...memory, version, entries: [...memory.entries, entry] });
    this.persistMemories();
  }
}
