import type {
  MonitoringClient,
  ResidentOverviewResponse,
} from "@/lib/monitoring";
import { residentOverviewFixture } from "./residents";

export class MockMonitoringClient implements MonitoringClient {
  async listResidentOverview(): Promise<ResidentOverviewResponse> {
    return structuredClone(residentOverviewFixture);
  }
}
