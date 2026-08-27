import type {
  MonitoringClient,
  ResidentOverviewResponse,
} from "@/lib/monitoring";
import { createResidentOverviewFixture } from "./residents";

export class MockMonitoringClient implements MonitoringClient {
  constructor(private readonly now: () => Date = () => new Date()) {}

  async listResidentOverview(): Promise<ResidentOverviewResponse> {
    return structuredClone(createResidentOverviewFixture(this.now()));
  }
}
