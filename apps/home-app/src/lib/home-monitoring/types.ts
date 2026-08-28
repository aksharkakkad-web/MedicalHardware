/**
 * Home-app presentation models. These are not Product API wire schemas.
 * A future real-data client must adapt the published DATA_CONTRACT domain
 * objects into these family-safe views instead of exposing clinic payloads.
 */
export const HOME_SCHEMA_VERSION = "1.0" as const;

export type HomeStatusState = "steady" | "attention" | "away" | "limited" | "unavailable";
export type HomeTrendDirection = "steady" | "changed" | "unavailable";

export interface HomeStatus {
  state: HomeStatusState;
  headline: string;
  summary: string;
  lastUpdatedAt: string;
}

export interface HomeTrend {
  trendId: "movement_routine" | "resting_pattern" | "time_at_home";
  label: string;
  direction: HomeTrendDirection;
  headline: string;
  summary: string;
  points: number[] | null;
}

export interface HomeUpdateSummary {
  eventId: string;
  headline: string;
  summary: string;
  occurredAt: string;
  importance: "important" | "notice";
  status: "new" | "explained";
}

export interface HomeActivityItem {
  activityId: string;
  label: string;
  occurredAt: string;
  kind: "status" | "routine" | "update";
}

export interface HomeOverviewResponse {
  schemaVersion: typeof HOME_SCHEMA_VERSION;
  generatedAt: string;
  lovedOne: {
    id: string;
    displayLabel: string;
    status: HomeStatus;
    trends: HomeTrend[];
    importantUpdate: HomeUpdateSummary | null;
    recentActivity: HomeActivityItem[];
  };
}

export interface HomeFeedbackSummary {
  outcome: "expected" | "not_expected" | "unsure";
  note: string;
  shouldRememberRoutine: boolean;
  savedAt: string;
}

export interface HomeUpdateDetail extends HomeUpdateSummary {
  schemaVersion: typeof HOME_SCHEMA_VERSION;
  whatChanged: string;
  observations: string[];
  limitation: string;
  interpretation: string;
  checkInSuggestion: string;
  feedback: HomeFeedbackSummary | null;
}

export interface SaveHomeFeedbackInput {
  outcome: HomeFeedbackSummary["outcome"];
  note: string;
  shouldRememberRoutine: boolean;
}

export interface HomeRoutineEntry {
  routineId: string;
  description: string;
  status: "active" | "retired";
  createdAt: string;
  retiredAt: string | null;
  retirementReason: string | null;
}

export interface HomeRoutinesResponse {
  schemaVersion: typeof HOME_SCHEMA_VERSION;
  version: number;
  entries: HomeRoutineEntry[];
}

export interface AddHomeRoutineInput {
  expectedVersion: number;
  description: string;
}

export interface RetireHomeRoutineInput {
  expectedVersion: number;
  reason: string;
}
