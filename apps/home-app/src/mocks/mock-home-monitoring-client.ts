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

export class MockHomeMonitoringClient implements HomeMonitoringClient {
  private feedback: Record<string, HomeFeedbackSummary>;
  private routines: HomeRoutinesResponse;

  constructor(private readonly storage: HomeStorage | undefined = browserStorage()) {
    this.feedback = this.read<Record<string, HomeFeedbackSummary>>(FEEDBACK_KEY, {});
    this.routines = this.read<HomeRoutinesResponse>(ROUTINES_KEY, homeRoutinesFixture);
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
    const note = input.note.trim();
    if (note.length > 240) throw new Error("Keep the note to 240 characters or fewer.");
    if (!["expected", "not_expected", "unsure"].includes(input.outcome)) throw new Error("Choose the answer that fits best.");

    this.feedback[eventId] = {
      outcome: input.outcome,
      note,
      shouldRememberRoutine: input.shouldRememberRoutine,
      savedAt: new Date().toISOString(),
    };
    this.write(FEEDBACK_KEY, this.feedback);
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

  private read<T>(key: string, fallback: T): T {
    try {
      const stored = this.storage?.getItem(key);
      return stored ? JSON.parse(stored) as T : clone(fallback);
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
