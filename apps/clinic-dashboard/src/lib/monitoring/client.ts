import type { ResidentOverviewResponse } from "./types";

export interface MonitoringClient {
  listResidentOverview(): Promise<ResidentOverviewResponse>;
}
