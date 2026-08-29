import type {
  AddHomeRoutineInput,
  HomeOverviewResponse,
  HomeRoutinesResponse,
  HomeUpdateDetail,
  RetireHomeRoutineInput,
  SaveHomeFeedbackInput,
} from "./types";

export interface HomeMonitoringClient {
  getOverview(): Promise<HomeOverviewResponse>;
  getUpdate(eventId: string): Promise<HomeUpdateDetail | null>;
  saveUpdateFeedback(eventId: string, input: SaveHomeFeedbackInput): Promise<HomeUpdateDetail>;
  getRoutines(): Promise<HomeRoutinesResponse>;
  addRoutine(input: AddHomeRoutineInput): Promise<HomeRoutinesResponse>;
  retireRoutine(routineId: string, input: RetireHomeRoutineInput): Promise<HomeRoutinesResponse>;
}
