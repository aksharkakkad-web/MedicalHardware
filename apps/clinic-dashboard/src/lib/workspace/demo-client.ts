import type { MonitoringClient, ResidentOverviewItem } from "@/lib/monitoring";
import { MockMonitoringClient } from "@/mocks/mock-monitoring-client";
import type { WorkspaceClient } from "./client";
import { parseRosterCsv } from "./roster";
import { WORKSPACE_PERMISSIONS } from "./permissions";
import { coreResidentIds, seedWorkspace } from "./seed";
import type {
  AddContextInput,
  AddFollowUpInput,
  AssignmentHistory,
  CareArea,
  CheckRecord,
  ContextRecord,
  Facility,
  FollowUp,
  NotificationTestResult,
  RecordCheckInput,
  ResidentMeasurement,
  ResidentProfile,
  ResolveConcernInput,
  RosterColumnMapping,
  RosterImportPreview,
  RosterImportRow,
  SaveResidentInput,
  SharedClient,
  WorkspaceSnapshot,
  WorkspacePermission,
} from "./types";
export interface WorkspaceStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}
export interface DemoWorkspaceOptions {
  monitoringClient?: MonitoringClient;
  storage?: WorkspaceStorage;
  now?: () => Date;
  clientId?: string;
  sourceObservedAt?: Date;
}
type Command = {
  requestId: string;
  eventId: string;
  action: "acknowledge" | "check" | "resolve";
  feedback?: ResolveConcernInput;
  clientLabel?: string;
  recordedAt?: string;
};
interface StoredState extends ReturnType<typeof seedWorkspace> {
  schemaVersion: 1;
  synthetic: true;
  version: number;
  nextId: number;
  sourceObservedAt: string;
  checks: CheckRecord[];
  imports: RosterImportPreview[];
  assignmentHistory: AssignmentHistory[];
  commands: Command[];
}
export const DEMO_WORKSPACE_STORAGE_KEY = "syren:synthetic-workspace:v1";
export const DEMO_STATION_STORAGE_KEY = "syren:synthetic-station:v1";
const queues = new Map<string, Promise<unknown>>();
const allowedPermissions = new Set<unknown>(WORKSPACE_PERMISSIONS);
const validOutcomes = new Set([
  "no_concern_observed",
  "concern_remains",
  "assistance_requested",
  "unable_to_check",
  "information_needs_review",
  "other",
]);
const clone = <T>(value: T): T => structuredClone(value);
function required(value: string, label: string) {
  if (!value?.trim()) throw new Error(`${label} is required.`);
  return value.trim();
}
function date(value: string, label: string): string {
  const parts =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|[+-]\d{2}:\d{2})$/.exec(
      value,
    );
  if (!parts || !Number.isFinite(Date.parse(value)))
    throw new Error(
      `${label} needs a valid ISO calendar date and explicit time zone.`,
    );
  const [, year, month, day, hour, minute, second] = parts;
  const y = Number(year),
    m = Number(month),
    d = Number(day);
  const leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (
    m < 1 ||
    m > 12 ||
    d < 1 ||
    d > days[m - 1] ||
    Number(hour) > 23 ||
    Number(minute) > 59 ||
    Number(second ?? 0) > 59
  )
    throw new Error(`${label} contains an impossible calendar date or time.`);
  return new Date(value).toISOString();
}
function stored(value: unknown): value is StoredState {
  if (!value || typeof value !== "object") return false;
  const s = value as Partial<StoredState>;
  return (
    s.schemaVersion === 1 &&
    s.synthetic === true &&
    Number.isInteger(s.version) &&
    Number.isInteger(s.nextId) &&
    typeof s.sourceObservedAt === "string" &&
    !!s.facility &&
    [
      "areas",
      "clients",
      "profiles",
      "contexts",
      "followUps",
      "checks",
      "imports",
      "assignmentHistory",
      "commands",
    ].every((k) => Array.isArray((s as unknown as Record<string, unknown>)[k]))
  );
}
/** Local synthetic workflow adapter. Core lifecycle transitions are delegated to MonitoringClient. */
export class DemoWorkspaceClient implements WorkspaceClient {
  readonly monitoringClient: MonitoringClient;
  private state: StoredState;
  private readonly now: () => Date;
  private readonly storage?: WorkspaceStorage;
  private readonly listeners = new Set<() => void>();
  private currentClientId: string;
  private currentAreaId = "all";
  private adminActive = false;
  private storageError: string | null = null;
  private readError = false;
  private loadedSavedState = false;
  private initialOverview: ResidentOverviewItem[] | null = null;
  constructor(options: DemoWorkspaceOptions = {}) {
    this.now = options.now ?? (() => new Date());
    this.storage = options.storage;
    const sourceObservedAt = (
      options.sourceObservedAt ?? this.now()
    ).toISOString();
    this.state = {
      ...seedWorkspace(sourceObservedAt),
      schemaVersion: 1,
      synthetic: true,
      version: 0,
      nextId: 1,
      sourceObservedAt,
      checks: [],
      imports: [],
      assignmentHistory: [],
      commands: [],
    };
    this.reload();
    if (this.storage && !this.readError && !this.loadedSavedState) {
      try {
        this.save(this.state);
      } catch {
        /* The snapshot exposes the storage failure; seed data stays local to this visit. */
      }
    }
    const frozenAt = new Date(this.state.sourceObservedAt);
    this.monitoringClient =
      options.monitoringClient ?? new MockMonitoringClient(() => frozenAt);
    this.currentClientId = options.clientId ?? "demo_station_01";
    if (!options.clientId && this.storage) {
      try {
        const value = this.storage.getItem(DEMO_STATION_STORAGE_KEY);
        if (value) {
          const perspective = JSON.parse(value) as {
            synthetic?: unknown;
            clientId?: unknown;
          };
          this.currentClientId =
            perspective.synthetic === true &&
            typeof perspective.clientId === "string"
              ? perspective.clientId
              : "unapproved_demo_client";
        }
      } catch {
        this.currentClientId = "unapproved_demo_client";
      }
    }
  }
  subscribe(listener: () => void) {
    this.listeners.add(listener);
    const onStorage = (event: StorageEvent) => {
      if (event.key === DEMO_WORKSPACE_STORAGE_KEY) listener();
    };
    if (typeof window !== "undefined")
      window.addEventListener("storage", onStorage);
    return () => {
      this.listeners.delete(listener);
      if (typeof window !== "undefined")
        window.removeEventListener("storage", onStorage);
    };
  }
  /** Used by the demo runtime when the shared monitoring scenario changes. */
  notifyMonitoringChanged() {
    this.emit();
  }
  hasRecordedEventWork(eventId: string) {
    this.reload();
    if (this.readError) throw new Error(this.storageError!);
    return (
      this.state.commands.some((command) => command.eventId === eventId) ||
      this.state.checks.some((check) => check.eventId === eventId) ||
      this.state.followUps.some((followUp) => followUp.eventId === eventId)
    );
  }
  private emit() {
    for (const listener of this.listeners) listener();
  }
  private reload() {
    if (!this.storage) return;
    try {
      const value = this.storage.getItem(DEMO_WORKSPACE_STORAGE_KEY);
      if (value) {
        const parsed: unknown = JSON.parse(value);
        if (!stored(parsed))
          throw new Error("Unrecognized synthetic demo state.");
        // Intentional local v1 migration: older synthetic stations without explicit grants
        // become view-only, including known seed IDs. Never infer authority from identity.
        // The migrated grant arrays are persisted with the next successful demo mutation.
        this.state = {
          ...parsed,
          clients: parsed.clients.map((client) => ({
            ...client,
            configurationVersion:
              Number.isSafeInteger(client.configurationVersion) &&
              client.configurationVersion >= 1
                ? client.configurationVersion
                : 1,
            permissions: Array.isArray(client.permissions)
              ? [
                  ...new Set(
                    client.permissions.filter((permission) =>
                      allowedPermissions.has(permission),
                    ),
                  ),
                ]
              : [],
          })),
        };
        this.loadedSavedState = true;
      }
      this.readError = false;
    } catch {
      this.readError = true;
      this.storageError =
        "Saved demo state could not be read. Local changes cannot be confirmed across a restart.";
    }
  }
  private save(next: StoredState) {
    if (this.storage) {
      try {
        this.storage.setItem(DEMO_WORKSPACE_STORAGE_KEY, JSON.stringify(next));
        this.storageError = null;
      } catch {
        this.storageError =
          "Demo storage could not save this change. Its saved state is not confirmed.";
        throw new Error(this.storageError);
      }
    }
    this.state = next;
  }
  private async mutate<T>(operation: () => Promise<T> | T): Promise<T> {
    const run = async () => {
      this.reload();
      if (this.readError) throw new Error(this.storageError!);
      await this.reconcile();
      const result = await operation();
      this.emit();
      return result;
    };
    const prior = queues.get(DEMO_WORKSPACE_STORAGE_KEY) ?? Promise.resolve();
    const task = prior
      .catch(() => undefined)
      .then(async () => {
        if (typeof navigator !== "undefined" && navigator.locks?.request)
          return navigator.locks.request(DEMO_WORKSPACE_STORAGE_KEY, run);
        return run();
      });
    queues.set(DEMO_WORKSPACE_STORAGE_KEY, task);
    return task;
  }
  private commit(change: (next: StoredState) => void) {
    const next = clone(this.state);
    change(next);
    next.version++;
    this.save(next);
  }
  private id(prefix: string) {
    return `${prefix}_${this.state.nextId++}`;
  }
  private station() {
    const station = this.state.clients.find(
      (c) => c.clientId === this.currentClientId,
    );
    if (!station)
      throw new Error(
        "This demo client is not approved. Ask an administrator to approve a station.",
      );
    return station;
  }
  private routine() {
    const station = this.station();
    if (station.status !== "approved")
      throw new Error(
        "This shared client is revoked. Ask an administrator for access.",
      );
    return station;
  }
  private requirePermission(permission: WorkspacePermission) {
    const station = this.routine();
    if (!station.permissions.includes(permission)) {
      const actions: Record<WorkspacePermission, string> = {
        acknowledge: "acknowledge concerns",
        record_check: "record resident check outcomes",
        resolve_concern: "resolve concerns",
        add_follow_up: "add follow-up work",
        update_follow_up: "complete or hand over follow-up work",
        report_context: "report resident context",
      };
      throw new Error(
        `This shared station is not permitted to ${actions[permission]}. Ask an administrator to review its permissions.`,
      );
    }
  }
  private permissionList(
    permissions: WorkspacePermission[],
  ): WorkspacePermission[] {
    if (
      !Array.isArray(permissions) ||
      permissions.some((permission) => !allowedPermissions.has(permission))
    )
      throw new Error("Choose supported station action permissions.");
    return [...new Set(permissions)];
  }
  private admin() {
    if (!this.adminActive)
      throw new Error("Enter demo administration to make this change.");
  }
  private profile(residentId: string) {
    const p = this.state.profiles.find((p) => p.residentId === residentId);
    if (!p) throw new Error("Resident could not be found.");
    if (!this.routine().areaIds.includes(p.areaId))
      throw new Error("This resident is outside this client’s coverage.");
    return p;
  }
  private async event(eventId: string) {
    const event = await this.monitoringClient.getEvent(eventId);
    this.profile(event.resident.residentId);
    return event;
  }
  private async reconcile() {
    for (const command of this.state.commands) {
      const event = await this.monitoringClient.getEvent(command.eventId);
      if (command.action === "acknowledge" && event.status === "open")
        await this.monitoringClient.performEventAction(
          command.eventId,
          "acknowledge",
        );
      if (command.action === "check" && event.status === "acknowledged")
        await this.monitoringClient.performEventAction(
          command.eventId,
          "check",
        );
      if (
        command.action === "resolve" &&
        event.status === "checked" &&
        command.feedback
      )
        await this.monitoringClient.resolveEventWithFeedback(
          command.eventId,
          command.feedback,
        );
    }
  }
  async snapshot(): Promise<WorkspaceSnapshot> {
    this.reload();
    if (this.readError) throw new Error(this.storageError!);
    await this.reconcile();
    const [overview, eventList] = await Promise.all([
      this.monitoringClient.listResidentOverview(),
      this.monitoringClient.listEvents(),
    ]);
    if (!this.initialOverview) this.initialOverview = clone(overview.items);
    const station = this.station();
    const approved = station.status === "approved";
    const profiles = this.state.profiles.filter(
      (p) => approved && station.areaIds.includes(p.areaId),
    );
    const ids = new Set(profiles.map((p) => p.residentId));
    const residents = profiles
      .filter((profile) => !profile.departedAt)
      .map((profile) => {
        const core = overview.items.find(
          (r) => r.residentId === profile.residentId,
        );
        const source = this.initialOverview?.find(
          (r) => r.residentId === profile.residentId,
        );
        const moved = !!source && source.roomId !== profile.roomId;
        if (core)
          return {
            ...core,
            displayLabel: profile.name,
            roomId: profile.roomId,
            roomLabel: profile.roomLabel,
            assignmentStatus: moved
              ? ("missing" as const)
              : core.assignmentStatus,
            monitoring: moved
              ? {
                  ...core.monitoring,
                  state: "unavailable" as const,
                  reason:
                    "New demo assignment needs backend validation and fresh measurements.",
                  lastUpdatedAt: profile.assignmentEffectiveAt,
                }
              : {
                  ...core.monitoring,
                  lastUpdatedAt:
                    source?.monitoring.lastUpdatedAt ??
                    core.monitoring.lastUpdatedAt,
                },
          };
        return {
          schemaVersion: "1.0",
          residentId: profile.residentId,
          displayLabel: profile.name,
          roomId: profile.roomId,
          roomLabel: profile.roomLabel,
          assignmentStatus: "missing",
          monitoring: {
            state: "unavailable",
            reason:
              "Manual demo roster record; no monitoring source is assigned.",
            lastUpdatedAt: profile.assignmentEffectiveAt,
          },
          attention: {
            priority: "none",
            headline: "Monitoring assignment needed",
            openEventCount: 0,
          },
          device: {
            status: "unknown",
            label: "No monitoring source assigned",
          },
        } satisfies ResidentOverviewItem;
      });
    const measurements: ResidentMeasurement[] = residents.flatMap(
      (resident) => {
        const index = coreResidentIds.indexOf(resident.residentId);
        const eligible =
          resident.assignmentStatus === "active" &&
          resident.monitoring.state === "active";
        return (["pulse", "breathing"] as const).map((kind) => ({
          residentId: resident.residentId,
          kind,
          label: kind === "pulse" ? "Pulse estimate" : "Breathing estimate",
          value: eligible
            ? kind === "pulse"
              ? 72 + index * 3
              : 15 + index
            : null,
          unit: kind === "pulse" ? "bpm" : "breaths/min",
          observedAt: eligible ? this.state.sourceObservedAt : null,
          quality: eligible ? "demo" : "unavailable",
          attribution: eligible ? "eligible" : "unavailable",
          reason: eligible
            ? "Synthetic demonstration estimate; not a real resident measurement."
            : resident.monitoring.reason,
          synthetic: true,
        }));
      },
    );
    const events = eventList.items
      .filter((e) => ids.has(e.resident.residentId))
      .map((event) => ({
        ...event,
        resident: {
          ...event.resident,
          displayLabel:
            this.state.profiles.find(
              (p) => p.residentId === event.resident.residentId,
            )?.name ?? event.resident.displayLabel,
        },
        feedback: event.feedback
          ? {
              ...event.feedback,
              createdAt:
                this.state.commands.find(
                  (c) => c.eventId === event.eventId && c.action === "resolve",
                )?.recordedAt ?? event.feedback.createdAt,
              submittedBy:
                this.state.commands.find(
                  (c) => c.eventId === event.eventId && c.action === "resolve",
                )?.clientLabel ?? event.feedback.submittedBy,
            }
          : null,
        actionHistory: event.actionHistory.map((item) => {
          const action =
            item.action === "acknowledged"
              ? "acknowledge"
              : item.action === "checked"
                ? "check"
                : item.action === "resolved"
                  ? "resolve"
                  : null;
          const command = this.state.commands.find(
            (c) => c.eventId === event.eventId && c.action === action,
          );
          return {
            ...item,
            actorLabel:
              command?.clientLabel ??
              (item.actorLabel === "Demo caregiver"
                ? "Synthetic shared-client action"
                : item.actorLabel),
            occurredAt: command?.recordedAt ?? item.occurredAt,
          };
        }),
      }));
    if (
      this.currentAreaId !== "all" &&
      !station.areaIds.includes(this.currentAreaId)
    )
      this.currentAreaId = "all";
    return clone({
      mode: "demo",
      demoNotice:
        "Synthetic demonstration · fictional residents and local browser workflow state. No production authentication, cross-device synchronization or notification delivery.",
      sourceObservedAt: this.state.sourceObservedAt,
      synchronizedAt: this.now().toISOString(),
      version: this.state.version,
      facility: this.state.facility,
      areas: this.adminActive
        ? this.state.areas
        : this.state.areas.filter(
            (area) => approved && station.areaIds.includes(area.areaId),
          ),
      currentClient: station,
      clients: this.adminActive ? this.state.clients : [station],
      currentAreaId: this.currentAreaId,
      admin: {
        active: this.adminActive,
        simulated: true,
      },
      residents,
      events,
      profiles,
      measurements,
      contexts: this.state.contexts.filter((c) => ids.has(c.residentId)),
      checks: this.state.checks.filter((c) => ids.has(c.residentId)),
      followUps: this.state.followUps.filter((f) => ids.has(f.residentId)),
      imports: this.adminActive ? this.state.imports : [],
      assignmentHistory: this.state.assignmentHistory.filter((a) =>
        ids.has(a.residentId),
      ),
      persistence: {
        available: !!this.storage && !this.storageError,
        message:
          this.storageError ??
          (this.storage
            ? "Synthetic demo changes persist in this browser. Same-browser tabs reconcile this journal; no backend or cross-device sync."
            : "Demo changes last for this visit only. Browser persistence is not available."),
      },
      capabilities: {
        authentication: false,
        serverSync: false,
        documentExtraction: false,
        xlsxImport: false,
        backgroundNotifications: false,
      },
    });
  }
  async setCurrentArea(areaId: string) {
    this.reload();
    if (areaId !== "all" && !this.routine().areaIds.includes(areaId))
      throw new Error("This area is outside this client’s coverage.");
    this.currentAreaId = areaId;
    this.emit();
  }
  async enterAdminSimulation() {
    await this.mutate(() => {
      this.commit(() => undefined);
      this.adminActive = true;
    });
  }
  async leaveAdminSimulation() {
    this.adminActive = false;
    this.emit();
  }
  async updateFacility(input: Omit<Facility, "facilityId">) {
    return this.mutate(() => {
      this.admin();
      const name = required(input.name, "Facility name");
      try {
        new Intl.DateTimeFormat("en", {
          timeZone: input.timeZone,
        });
      } catch {
        throw new Error("Choose a valid IANA time zone.");
      }
      const result = {
        ...input,
        name,
        facilityId: this.state.facility.facilityId,
      };
      this.commit((s) => {
        s.facility = result;
      });
      return clone(result);
    });
  }
  async saveArea(input: { areaId?: string; name: string }) {
    return this.mutate(() => {
      this.admin();
      const name = required(input.name, "Area name");
      if (
        this.state.areas.some(
          (a) =>
            a.name.toLowerCase() === name.toLowerCase() &&
            a.areaId !== input.areaId,
        )
      )
        throw new Error("An area with that name already exists.");
      const current = input.areaId
        ? this.state.areas.find((a) => a.areaId === input.areaId)
        : null;
      if (input.areaId && !current) throw new Error("Area could not be found.");
      const result: CareArea = {
        areaId: current?.areaId ?? this.id("area"),
        name,
        roomIds: current?.roomIds ?? [],
      };
      this.commit((s) => {
        s.areas = [
          ...s.areas.filter((a) => a.areaId !== result.areaId),
          result,
        ];
      });
      return clone(result);
    });
  }
  private areaIds(ids: string[]) {
    if (
      !ids.length ||
      ids.some((id) => !this.state.areas.some((a) => a.areaId === id))
    )
      throw new Error("Choose at least one valid coverage area.");
    return [...new Set(ids)];
  }
  async approveClient(input: {
    name: string;
    areaIds: string[];
    permissions?: WorkspacePermission[];
  }) {
    return this.mutate(() => {
      this.admin();
      const result: SharedClient = {
        clientId: this.id("demo_client"),
        name: required(input.name, "Shared client name"),
        areaIds: this.areaIds(input.areaIds),
        permissions: this.permissionList(input.permissions ?? []),
        configurationVersion: 1,
        status: "approved",
        approvedAt: this.now().toISOString(),
        notificationStatus: "not_configured",
      };
      this.commit((s) => {
        s.clients.push(result);
      });
      return clone(result);
    });
  }
  async updateClient(input: {
    clientId: string;
    name: string;
    areaIds: string[];
    permissions?: WorkspacePermission[];
    expectedConfigurationVersion?: number;
  }) {
    return this.mutate(() => {
      this.admin();
      const client = this.state.clients.find(
        (c) => c.clientId === input.clientId,
      );
      if (!client) throw new Error("Shared client could not be found.");
      if (
        input.expectedConfigurationVersion !== undefined &&
        input.expectedConfigurationVersion !== client.configurationVersion
      ) {
        throw new Error(
          "Station settings changed since this editor was opened. Reload the station settings before saving again.",
        );
      }
      const result = {
        ...client,
        configurationVersion: client.configurationVersion + 1,
        name: required(input.name, "Shared client name"),
        areaIds: this.areaIds(input.areaIds),
        permissions: this.permissionList(
          input.permissions ?? client.permissions,
        ),
      };
      this.commit((s) => {
        s.clients = s.clients.map((c) =>
          c.clientId === result.clientId ? result : c,
        );
      });
      return clone(result);
    });
  }
  async revokeClient(clientId: string) {
    await this.mutate(() => {
      this.admin();
      if (!this.state.clients.some((c) => c.clientId === clientId))
        throw new Error("Shared client could not be found.");
      this.commit((s) => {
        s.clients = s.clients.map((c) =>
          c.clientId === clientId
            ? {
                ...c,
                configurationVersion: c.configurationVersion + 1,
                status: "revoked",
              }
            : c,
        );
      });
    });
  }
  async selectDemoClient(clientId: string) {
    this.admin();
    this.reload();
    if (!this.state.clients.some((c) => c.clientId === clientId))
      throw new Error("Shared client could not be found.");
    if (this.storage) {
      try {
        this.storage.setItem(
          DEMO_STATION_STORAGE_KEY,
          JSON.stringify({
            synthetic: true,
            clientId,
          }),
        );
      } catch {
        this.storageError =
          "Demo storage could not save this station selection. Its saved state is not confirmed.";
        throw new Error(this.storageError);
      }
    }
    this.currentClientId = clientId;
    this.currentAreaId = "all";
    this.emit();
  }
  private residentInput(input: SaveResidentInput): ResidentProfile {
    const name = required(input.name, "Synthetic resident name");
    const facilityResidentId = required(
      input.facilityResidentId,
      "Facility resident identifier",
    );
    const area = this.state.areas.find((a) => a.areaId === input.areaId);
    if (!area) throw new Error("Choose a valid area.");
    const existing = input.residentId
      ? this.state.profiles.find((p) => p.residentId === input.residentId)
      : null;
    if (input.residentId && !existing)
      throw new Error("Resident could not be found.");
    if (
      this.state.profiles.some(
        (p) =>
          p.facilityResidentId.toLowerCase() ===
            facilityResidentId.toLowerCase() &&
          p.residentId !== input.residentId,
      )
    )
      throw new Error("That facility resident identifier is already in use.");
    const roomLabel = required(input.roomLabel, "Room label");
    if (
      this.state.profiles.some(
        (p) =>
          !p.departedAt &&
          p.roomLabel.toLowerCase() === roomLabel.toLowerCase() &&
          p.residentId !== input.residentId,
      )
    )
      throw new Error(
        "Assignment conflict: the room already has an active resident.",
      );
    const knownRoom = this.state.profiles.find(
      (p) => p.roomLabel.toLowerCase() === roomLabel.toLowerCase(),
    );
    const roomId = knownRoom?.roomId ?? this.id("demo_room");
    const effectiveAt = input.effectiveAt
      ? date(input.effectiveAt, "Effective time")
      : this.now().toISOString();
    if (Date.parse(effectiveAt) > this.now().getTime())
      throw new Error("Future assignments are not supported by this demo.");
    const admittedAt = input.admittedAt
      ? date(input.admittedAt, "Admission time")
      : (existing?.admittedAt ?? effectiveAt);
    const departedAt = input.departedAt
      ? date(input.departedAt, "Departure time")
      : input.departedAt === null
        ? null
        : (existing?.departedAt ?? null);
    if (Date.parse(admittedAt) > this.now().getTime())
      throw new Error("Future admissions are not supported by this demo.");
    if (departedAt && Date.parse(departedAt) > this.now().getTime())
      throw new Error("Future departures are not supported by this demo.");
    if (departedAt && Date.parse(departedAt) < Date.parse(admittedAt))
      throw new Error("Departure cannot be earlier than admission.");
    return {
      residentId: existing?.residentId ?? this.id("demo_resident"),
      name,
      facilityResidentId,
      areaId: area.areaId,
      roomId,
      roomLabel,
      admittedAt,
      departedAt,
      assignmentEffectiveAt:
        existing?.roomId === roomId && existing.areaId === area.areaId
          ? existing.assignmentEffectiveAt
          : effectiveAt,
      synthetic: true,
    };
  }
  private writeResident(next: StoredState, profile: ResidentProfile) {
    const old = next.profiles.find((p) => p.residentId === profile.residentId);
    next.profiles = [
      ...next.profiles.filter((p) => p.residentId !== profile.residentId),
      profile,
    ];
    if (!old || old.roomId !== profile.roomId || old.areaId !== profile.areaId)
      next.assignmentHistory.push({
        residentId: profile.residentId,
        fromRoomId: old?.roomId ?? null,
        toRoomId: profile.roomId,
        effectiveAt: profile.assignmentEffectiveAt,
        recordedAt: this.now().toISOString(),
      });
    next.areas = next.areas.map((area) => ({
      ...area,
      roomIds: [
        ...new Set(
          next.profiles
            .filter((p) => p.areaId === area.areaId && !p.departedAt)
            .map((p) => p.roomId),
        ),
      ],
    }));
  }
  async saveResident(input: SaveResidentInput) {
    return this.mutate(() => {
      this.admin();
      const result = this.residentInput(input);
      this.commit((s) => this.writeResident(s, result));
      return clone(result);
    });
  }
  async acknowledgeEvent(eventId: string, requestId?: string) {
    await this.mutate(async () => {
      this.requirePermission("acknowledge");
      await this.event(eventId);
      const key = requestId ?? this.id("ack");
      const prior = this.state.commands.find((c) => c.requestId === key);
      if (prior) {
        if (prior.eventId !== eventId || prior.action !== "acknowledge")
          throw new Error("Retry identifier belongs to a different action.");
        return;
      }
      const event = await this.event(eventId);
      if (event.status === "resolved")
        throw new Error("Resolved history is immutable.");
      if (event.status !== "open")
        throw new Error(
          "This event was already acknowledged. Refresh its current response.",
        );
      // Save the validated demo journal before advancing the shared core lifecycle.
      this.commit((s) =>
        s.commands.push({
          requestId: key,
          eventId,
          action: "acknowledge",
          clientLabel: this.station().name,
          recordedAt: this.now().toISOString(),
        }),
      );
      await this.monitoringClient.performEventAction(eventId, "acknowledge");
    });
  }
  async recordCheck(eventId: string, input: RecordCheckInput) {
    return this.mutate(async () => {
      this.requirePermission("record_check");
      if (!validOutcomes.has(input.outcome))
        throw new Error("Choose a supported check outcome.");
      const note = input.note?.trim() ?? "";
      if (input.outcome === "other" && !note)
        throw new Error("Add a short explanation note for another outcome.");
      const key = input.requestId ?? this.id("check_request");
      const prior = this.state.checks.find((c) => c.requestId === key);
      if (prior) {
        this.profile(prior.residentId);
        if (
          prior.eventId !== eventId ||
          prior.outcome !== input.outcome ||
          prior.note !== note
        )
          throw new Error("Retry identifier belongs to a different check.");
        return clone(prior);
      }
      if (this.state.commands.some((c) => c.requestId === key))
        throw new Error("Retry identifier belongs to a different action.");
      const event = await this.event(eventId);
      if (event.status === "resolved")
        throw new Error(
          "Resolved history is immutable; record new work separately.",
        );
      if (event.status === "open" || event.status === "detected")
        throw new Error("Acknowledge this concern before recording a check.");
      const checkedAt = input.checkedAt
        ? date(input.checkedAt, "Reported check time")
        : this.now().toISOString();
      if (Date.parse(checkedAt) > this.now().getTime())
        throw new Error("Reported check time cannot be in the future.");
      const completedCheck = [
        "no_concern_observed",
        "concern_remains",
        "assistance_requested",
      ].includes(input.outcome);
      const needsFollowUp = input.outcome !== "no_concern_observed";
      const station = this.routine();
      const result: CheckRecord = {
        checkId: this.id("check"),
        eventId,
        residentId: event.resident.residentId,
        outcome: input.outcome,
        note,
        checkedAt,
        recordedAt: this.now().toISOString(),
        clientId: station.clientId,
        clientLabel: station.name,
        completedCheck,
        requestId: key,
      };
      const text: Record<string, string> = {
        concern_remains:
          "Concern remains after the reported check. Review and continue the facility response.",
        assistance_requested:
          "Further assistance was requested. Confirm the outcome; arrival has not been established.",
        unable_to_check:
          "Resident check could not be completed. Arrange another check or hand over the unfinished work.",
        information_needs_review:
          "Room, assignment or monitoring information needs review. Resident check is not established.",
        other: "Review the reported exception and confirm the next step.",
      };
      this.commit((s) => {
        s.checks.push(result);
        if (completedCheck)
          s.commands.push({
            requestId: key,
            eventId,
            action: "check",
            clientLabel: station.name,
            recordedAt: result.recordedAt,
          });
        if (needsFollowUp)
          s.followUps.push({
            followUpId: `followup_${result.checkId}`,
            residentId: result.residentId,
            eventId,
            text: `${text[input.outcome]}${note ? " " + note : ""}`,
            createdAt: result.recordedAt,
            dueAt: null,
            status: "open",
            completionNote: null,
            completedAt: null,
            clientLabel: station.name,
          });
      });
      if (completedCheck && event.status === "acknowledged")
        await this.monitoringClient.performEventAction(eventId, "check");
      return clone(result);
    });
  }
  async resolveEvent(eventId: string, input: ResolveConcernInput) {
    await this.mutate(async () => {
      this.requirePermission("resolve_concern");
      const key = input.requestId ?? this.id("resolve");
      const prior = this.state.commands.find((c) => c.requestId === key);
      if (prior) {
        if (
          prior.eventId !== eventId ||
          prior.action !== "resolve" ||
          prior.feedback?.outcome !== input.outcome ||
          prior.feedback?.actualEventLabel !== input.actualEventLabel
        )
          throw new Error(
            "Retry identifier belongs to a different resolution.",
          );
        this.profile(
          (await this.monitoringClient.getEvent(eventId)).resident.residentId,
        );
        return;
      }
      const event = await this.event(eventId);
      if (event.status === "resolved")
        throw new Error("Resolved event history is immutable.");
      if (!["confirmed", "false_positive", "uncertain"].includes(input.outcome))
        throw new Error("Choose a supported resolution outcome.");
      required(input.actualEventLabel, "Resolution description");
      const latest = this.state.checks
        .filter((c) => c.eventId === eventId)
        .at(-1);
      if (event.status !== "checked" || (latest && !latest.completedCheck))
        throw new Error(
          "A completed resident check is required before resolution.",
        );
      if (
        this.state.followUps.some(
          (f) => f.eventId === eventId && f.status !== "completed",
        )
      )
        throw new Error(
          "Complete outstanding follow-up before resolving this event.",
        );
      this.commit((s) =>
        s.commands.push({
          requestId: key,
          eventId,
          action: "resolve",
          feedback: input,
          clientLabel: this.station().name,
          recordedAt: this.now().toISOString(),
        }),
      );
      await this.monitoringClient.resolveEventWithFeedback(eventId, input);
    });
  }
  async addContext(residentId: string, input: AddContextInput) {
    return this.mutate(() => {
      if (!this.adminActive) this.requirePermission("report_context");
      this.profile(residentId);
      const text = required(input.text, "Observation or correction");
      const superseded = input.supersedesContextId
        ? this.state.contexts.find(
            (c) =>
              c.contextId === input.supersedesContextId &&
              c.residentId === residentId,
          )
        : null;
      if (input.supersedesContextId && !superseded)
        throw new Error(
          "The source context could not be found for this resident.",
        );
      const result: ContextRecord = {
        contextId: this.id("context"),
        residentId,
        category: input.category ?? "observation",
        text,
        source:
          input.source?.trim() ||
          `Reported from ${this.station().name} · identity unverified`,
        recordedAt: this.now().toISOString(),
        effectiveUntil: input.effectiveUntil
          ? date(input.effectiveUntil, "Context expiration")
          : null,
        reviewStatus: "needs_review",
        supersedesContextId: superseded?.contextId ?? null,
      };
      this.commit((s) => s.contexts.push(result));
      return clone(result);
    });
  }
  async addFollowUp(input: AddFollowUpInput) {
    return this.mutate(async () => {
      this.requirePermission("add_follow_up");
      this.profile(input.residentId);
      if (input.eventId) {
        const event = await this.event(input.eventId);
        if (event.resident.residentId !== input.residentId)
          throw new Error("Follow-up resident does not match this event.");
      }
      const result: FollowUp = {
        followUpId: this.id("followup"),
        residentId: input.residentId,
        eventId: input.eventId ?? null,
        text: required(input.text, "Follow-up detail"),
        createdAt: this.now().toISOString(),
        dueAt: input.dueAt ? date(input.dueAt, "Follow-up time") : null,
        status: "open",
        completionNote: null,
        completedAt: null,
        clientLabel: this.station().name,
      };
      this.commit((s) => s.followUps.push(result));
      return clone(result);
    });
  }
  private followUp(id: string) {
    const followUp = this.state.followUps.find((f) => f.followUpId === id);
    if (!followUp) throw new Error("Follow-up could not be found.");
    this.profile(followUp.residentId);
    return followUp;
  }
  async completeFollowUp(id: string, note = "") {
    await this.mutate(() => {
      this.requirePermission("update_follow_up");
      const followUp = this.followUp(id);
      if (followUp.status === "completed") return;
      this.commit((s) => {
        s.followUps = s.followUps.map((f) =>
          f.followUpId === id
            ? {
                ...f,
                status: "completed",
                completionNote: note.trim() || null,
                history: [
                  ...(f.history ?? []),
                  {
                    action: "completed" as const,
                    note: note.trim() || null,
                    recordedAt: this.now().toISOString(),
                    clientLabel: this.station().name,
                  },
                ],
                completedAt: this.now().toISOString(),
                clientLabel: this.station().name,
              }
            : f,
        );
      });
    });
  }
  async handOverFollowUp(id: string, note: string) {
    await this.mutate(() => {
      this.requirePermission("update_follow_up");
      const followUp = this.followUp(id);
      if (followUp.status === "completed")
        throw new Error("Completed follow-up is historical.");
      const detail = required(note, "Handover detail");
      this.commit((s) => {
        s.followUps = s.followUps.map((f) =>
          f.followUpId === id
            ? {
                ...f,
                status: "handed_over",
                completionNote: detail,
                history: [
                  ...(f.history ?? []),
                  {
                    action: "handed_over" as const,
                    note: detail,
                    recordedAt: this.now().toISOString(),
                    clientLabel: this.station().name,
                  },
                ],
                clientLabel: this.station().name,
              }
            : f,
        );
      });
    });
  }
  async previewRosterCsv(
    csv: string,
    fileName = "synthetic-roster.csv",
    mapping: RosterColumnMapping = {},
  ) {
    return this.mutate(() => {
      this.admin();
      const { headers, rows } = parseRosterCsv(csv);
      const aliases = {
        facilityResidentId: [
          "facilityresidentid",
          "resident_id",
          "residentid",
          "id",
        ],
        name: ["name", "residentname", "resident_name"],
        roomLabel: ["roomlabel", "room", "room_label"],
        areaName: ["areaname", "area", "area_name"],
      };
      const fields = Object.keys(aliases) as Array<keyof RosterColumnMapping>;
      const column = (field: keyof RosterColumnMapping) =>
        mapping[field]
          ? headers.indexOf(mapping[field]!)
          : headers.findIndex((h) => aliases[field].includes(h.toLowerCase()));
      const absent = fields.filter((field) => column(field) < 0);
      if (absent.length)
        throw new Error(`CSV is missing mapped columns: ${absent.join(", ")}.`);
      const seenIds = new Set<string>();
      const seenRooms = new Set<string>();
      const resultRows: RosterImportRow[] = rows.map((values, index) => {
        const read = (field: keyof RosterColumnMapping) =>
          values[column(field)]?.trim() ?? "";
        const facilityResidentId = read("facilityResidentId"),
          name = read("name"),
          roomLabel = read("roomLabel"),
          areaName = read("areaName");
        const issues: string[] = [];
        if (values.length !== headers.length)
          issues.push("Row has a different number of fields from the header.");
        if (!facilityResidentId || !name || !roomLabel || !areaName)
          issues.push("Identifier, name, room and area are required.");
        const idKey = facilityResidentId.toLowerCase(),
          roomKey = roomLabel.toLowerCase();
        if (seenIds.has(idKey))
          issues.push("Duplicate facility resident identifier in this file.");
        if (seenRooms.has(roomKey))
          issues.push("Conflicting room assignments in this file.");
        seenIds.add(idKey);
        seenRooms.add(roomKey);
        const existing = this.state.profiles.find(
          (p) => p.facilityResidentId.toLowerCase() === idKey,
        );
        const area = this.state.areas.find(
          (a) => a.name.toLowerCase() === areaName.toLowerCase(),
        );
        if (!area)
          issues.push("Area is unmatched; create or map it before importing.");
        if (
          this.state.profiles.some(
            (p) =>
              p.name.toLowerCase() === name.toLowerCase() &&
              p.facilityResidentId.toLowerCase() !== idKey,
          )
        )
          issues.push(
            "Possible duplicate name with a different identifier; review identity.",
          );
        if (
          this.state.profiles.some(
            (p) =>
              !p.departedAt &&
              p.roomLabel.toLowerCase() === roomKey &&
              p.residentId !== existing?.residentId,
          )
        )
          issues.push("Assignment conflict with an existing occupant.");
        return {
          rowNumber: index + 2,
          facilityResidentId,
          name,
          roomLabel,
          areaName,
          issues,
          action: issues.length ? "blocked" : existing ? "update" : "add",
          residentId: existing?.residentId ?? null,
        };
      });
      for (const row of resultRows) {
        if (
          resultRows.filter(
            (other) =>
              other.facilityResidentId.toLowerCase() ===
              row.facilityResidentId.toLowerCase(),
          ).length > 1 &&
          !row.issues.some((issue) => issue.startsWith("Duplicate"))
        )
          row.issues.push(
            "Duplicate facility resident identifier in this file.",
          );
        if (
          resultRows.filter(
            (other) =>
              other.roomLabel.toLowerCase() === row.roomLabel.toLowerCase(),
          ).length > 1 &&
          !row.issues.some((issue) => issue.startsWith("Conflicting"))
        )
          row.issues.push("Conflicting room assignments in this file.");
        if (row.issues.length) row.action = "blocked";
      }
      const result: RosterImportPreview = {
        importId: this.id("import"),
        fileName: required(fileName, "File name"),
        createdAt: this.now().toISOString(),
        expectedVersion: this.state.version + 1,
        rows: resultRows,
        canApply:
          resultRows.length > 0 && resultRows.every((r) => !r.issues.length),
        status:
          resultRows.length && resultRows.every((r) => !r.issues.length)
            ? "ready_for_review"
            : "rejected",
        appliedAt: null,
        synthetic: true,
      };
      this.commit((s) => s.imports.push(result));
      return clone(result);
    });
  }
  async applyRosterImport(importId: string) {
    return this.mutate(() => {
      this.admin();
      const preview = this.state.imports.find((i) => i.importId === importId);
      if (!preview) throw new Error("Import preview could not be found.");
      if (preview.status === "applied") return clone(preview);
      if (!preview.canApply)
        throw new Error(
          "Resolve import conflicts and review a new preview before applying.",
        );
      if (preview.expectedVersion !== this.state.version)
        throw new Error(
          "Workspace changed after this preview. Preview the roster again.",
        );
      const additions = preview.rows.map((row) =>
        this.residentInput({
          residentId: row.residentId ?? undefined,
          name: row.name,
          facilityResidentId: row.facilityResidentId,
          roomLabel: row.roomLabel,
          areaId: this.state.areas.find(
            (a) => a.name.toLowerCase() === row.areaName.toLowerCase(),
          )!.areaId,
        }),
      );
      const result: RosterImportPreview = {
        ...preview,
        status: "applied",
        canApply: false,
        appliedAt: this.now().toISOString(),
      };
      this.commit((s) => {
        for (const resident of additions) this.writeResident(s, resident);
        s.imports = s.imports.map((i) =>
          i.importId === importId ? result : i,
        );
      });
      return clone(result);
    });
  }
  async testNotifications(
    clientId = this.currentClientId,
  ): Promise<NotificationTestResult> {
    this.reload();
    if (clientId !== this.currentClientId) this.admin();
    const client = this.state.clients.find((c) => c.clientId === clientId);
    if (!client) throw new Error("Shared client could not be found.");
    return {
      status: "blocked",
      testedAt: this.now().toISOString(),
      clientId,
      delivered: false,
      reason:
        client.status === "revoked"
          ? "This shared client is revoked. No notification was sent."
          : "No server notification sender, push subscription or validated independent route is connected. No test was sent or delivered. Browser permission alone is not a delivery test.",
    };
  }
}
