import type {
  AddHomeRoutineInput,
  HomeFeedbackSummary,
  HomeMonitoringClient,
  HomeOverviewResponse,
  HomeRoutinesResponse,
  HomeUpdateDetail,
  RetireHomeRoutineInput,
  SaveHomeFeedbackInput,
} from "@/lib/home-monitoring";
import { HOME_UPDATE_ID, homeOverviewFixture, homeRoutinesFixture, homeUpdateFixture } from "./home-fixtures";

const FEEDBACK_KEY = "adaptive-care:home-feedback:v1";
const ROUTINES_KEY = "adaptive-care:home-routines:v1";

export interface HomeStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}

function browserStorage(): HomeStorage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDateString(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isFeedback(value: unknown): value is HomeFeedbackSummary {
  if (!isRecord(value)) return false;
  return ["expected", "not_expected", "unsure"].includes(String(value.outcome))
    && typeof value.note === "string"
    && typeof value.shouldRememberRoutine === "boolean"
    && isDateString(value.savedAt);
}

function isFeedbackStore(value: unknown): value is Record<string, HomeFeedbackSummary> {
  return isRecord(value) && Object.values(value).every(isFeedback);
}

function isRoutinesResponse(value: unknown): value is HomeRoutinesResponse {
  if (!isRecord(value) || value.schemaVersion !== "1.0" || typeof value.version !== "number" || !Array.isArray(value.entries)) return false;
  return value.entries.every((entry) => {
    if (!isRecord(entry)
      || typeof entry.routineId !== "string"
      || typeof entry.description !== "string"
      || !["active", "retired"].includes(String(entry.status))
      || !isDateString(entry.createdAt)) return false;
    if (entry.status === "active") return entry.retiredAt === null && entry.retirementReason === null;
    return isDateString(entry.retiredAt) && typeof entry.retirementReason === "string" && entry.retirementReason.trim().length > 0;
  });
}

export class MockHomeMonitoringClient implements HomeMonitoringClient {
  private feedback: Record<string, HomeFeedbackSummary>;
  private routines: HomeRoutinesResponse;

  constructor(private readonly storage: HomeStorage | undefined = browserStorage()) {
    this.feedback = this.read(FEEDBACK_KEY, {}, isFeedbackStore);
    this.routines = this.read(ROUTINES_KEY, homeRoutinesFixture, isRoutinesResponse);
  }

  async getOverview(): Promise<HomeOverviewResponse> {
    const overview = clone(homeOverviewFixture);
    if (this.feedback[HOME_UPDATE_ID] && overview.lovedOne.importantUpdate) {
      overview.lovedOne.importantUpdate.status = "explained";
    }
    return overview;
  }

  async getUpdate(eventId: string): Promise<HomeUpdateDetail | null> {
    if (eventId !== HOME_UPDATE_ID) return null;
    const update = clone(homeUpdateFixture);
    update.feedback = clone(this.feedback[eventId] ?? null);
    update.status = update.feedback ? "explained" : "new";
    return update;
  }

  async saveUpdateFeedback(eventId: string, input: SaveHomeFeedbackInput): Promise<HomeUpdateDetail> {
    if (eventId !== HOME_UPDATE_ID) throw new Error("This update could not be found.");
    if (this.feedback[eventId]) return (await this.getUpdate(eventId)) as HomeUpdateDetail;
    const note = input.note.trim();
    if (note.length > 240) throw new Error("Keep the note to 240 characters or fewer.");
    if (!["expected", "not_expected", "unsure"].includes(input.outcome)) throw new Error("Choose the answer that fits best.");
    if (input.shouldRememberRoutine && note.length < 4) throw new Error("Add a short note to describe the routine you want remembered.");
    if (input.shouldRememberRoutine && note.length > 160) throw new Error("Keep a remembered routine to 160 characters or fewer.");

    this.feedback[eventId] = {
      outcome: input.outcome,
      note,
      shouldRememberRoutine: input.shouldRememberRoutine,
      savedAt: new Date().toISOString(),
    };
    this.write(FEEDBACK_KEY, this.feedback);
    if (input.shouldRememberRoutine) {
      await this.addRoutine({ expectedVersion: this.routines.version, description: note });
    }
    return (await this.getUpdate(eventId)) as HomeUpdateDetail;
  }

  async getRoutines(): Promise<HomeRoutinesResponse> {
    return clone(this.routines);
  }

  async addRoutine(input: AddHomeRoutineInput): Promise<HomeRoutinesResponse> {
    this.assertVersion(input.expectedVersion);
    const description = input.description.trim();
    if (description.length < 4) throw new Error("Describe the routine in a little more detail.");
    if (description.length > 160) throw new Error("Keep the routine to 160 characters or fewer.");

    this.routines = {
      ...this.routines,
      version: this.routines.version + 1,
      entries: [{
        routineId: `routine_${Date.now()}`,
        description,
        status: "active",
        createdAt: new Date().toISOString(),
        retiredAt: null,
        retirementReason: null,
      }, ...this.routines.entries],
    };
    this.write(ROUTINES_KEY, this.routines);
    return clone(this.routines);
  }

  async retireRoutine(routineId: string, input: RetireHomeRoutineInput): Promise<HomeRoutinesResponse> {
    this.assertVersion(input.expectedVersion);
    const reason = input.reason.trim();
    if (reason.length < 3) throw new Error("Add a short reason so this history still makes sense.");
    if (reason.length > 120) throw new Error("Keep the reason to 120 characters or fewer.");
    const existing = this.routines.entries.find((entry) => entry.routineId === routineId && entry.status === "active");
    if (!existing) throw new Error("This routine is no longer active.");

    this.routines = {
      ...this.routines,
      version: this.routines.version + 1,
      entries: this.routines.entries.map((entry) => entry.routineId === routineId ? {
        ...entry,
        status: "retired" as const,
        retiredAt: new Date().toISOString(),
        retirementReason: reason,
      } : entry),
    };
    this.write(ROUTINES_KEY, this.routines);
    return clone(this.routines);
  }

  private assertVersion(expectedVersion: number) {
    if (expectedVersion !== this.routines.version) {
      throw new Error("The routine list changed. Refresh and try again.");
    }
  }

  private read<T>(key: string, fallback: T, validates: (value: unknown) => value is T): T {
    try {
      const stored = this.storage?.getItem(key);
      if (!stored) return clone(fallback);
      const parsed: unknown = JSON.parse(stored);
      return validates(parsed) ? clone(parsed) : clone(fallback);
    } catch {
      return clone(fallback);
    }
  }

  private write(key: string, value: unknown) {
    try {
      this.storage?.setItem(key, JSON.stringify(value));
    } catch {
      // The current visit still works even when browser storage is unavailable.
    }
  }
}
