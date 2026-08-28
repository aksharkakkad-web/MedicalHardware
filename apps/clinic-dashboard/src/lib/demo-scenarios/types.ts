export type DemoScenarioId =
  | "resident_away"
  | "resident_returned"
  | "possible_multi_person"
  | "physiological_deviation";

export type DemoScenarioTone = "neutral" | "healthy" | "attention" | "critical";

export interface DemoScenarioDefinition {
  scenarioId: DemoScenarioId;
  label: string;
  summary: string;
  safetyRule: string;
  expectedOutcomes: [string, string, string];
  tone: DemoScenarioTone;
  targetKind: "resident" | "event";
}

export interface DemoScenarioState {
  schemaVersion: "1.0";
  activeScenarioId: DemoScenarioId | null;
  appliedAt: string | null;
  targetResidentId: string;
  targetEventId: string | null;
  persistenceAvailable: boolean;
}

export interface DemoScenarioController {
  listDemoScenarios(): Promise<DemoScenarioDefinition[]>;
  getActiveDemoScenario(): Promise<DemoScenarioState>;
  applyDemoScenario(scenarioId: DemoScenarioId): Promise<DemoScenarioState>;
  resetDemoScenario(): Promise<DemoScenarioState>;
}
