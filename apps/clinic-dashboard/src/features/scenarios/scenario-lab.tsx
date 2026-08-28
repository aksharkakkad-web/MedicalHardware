"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ArrowIcon } from "@/components/icons/icons";
import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import {
  useDemoScenarioController,
  type DemoScenarioDefinition,
  type DemoScenarioId,
  type DemoScenarioState,
} from "@/lib/demo-scenarios";

import styles from "./scenario-lab.module.css";

type LabData = {
  definitions: DemoScenarioDefinition[];
  state: DemoScenarioState;
};

type LoadState =
  | { status: "loading" }
  | { status: "unavailable" }
  | { status: "error"; message: string }
  | { status: "success"; data: LabData };

const toneMap: Record<DemoScenarioDefinition["tone"], StatusTone> = {
  neutral: "neutral",
  healthy: "healthy",
  attention: "attention",
  critical: "critical",
};

function formattedTime(value: string | null): string {
  if (!value) return "Not run yet";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function ScenarioLab() {
  const controller = useDemoScenarioController();
  const [result, setResult] = useState<LoadState>(controller ? { status: "loading" } : { status: "unavailable" });
  const [running, setRunning] = useState<DemoScenarioId | "reset" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    if (!controller) {
      return () => { current = false; };
    }
    Promise.all([controller.listDemoScenarios(), controller.getActiveDemoScenario()])
      .then(([definitions, state]) => { if (current) setResult({ status: "success", data: { definitions, state } }); })
      .catch(() => { if (current) setResult({ status: "error", message: "The demo walkthrough state could not be opened." }); });
    return () => { current = false; };
  }, [controller]);

  async function runScenario(scenarioId: DemoScenarioId) {
    if (!controller || result.status !== "success") return;
    setRunning(scenarioId);
    setMessage(null);
    try {
      const state = await controller.applyDemoScenario(scenarioId);
      setResult({ status: "success", data: { ...result.data, state } });
      setMessage(state.persistenceAvailable ? "Scenario applied to the clinic demo." : "Scenario applied for this visit, but this browser could not save it for later.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The scenario could not be applied.");
    } finally {
      setRunning(null);
    }
  }

  async function resetScenario() {
    if (!controller || result.status !== "success") return;
    setRunning("reset");
    setMessage(null);
    try {
      const state = await controller.resetDemoScenario();
      setResult({ status: "success", data: { ...result.data, state } });
      setMessage("Baseline demo restored.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The demo could not be reset.");
    } finally {
      setRunning(null);
    }
  }

  if (result.status === "loading") return <div className={styles.message} role="status">Opening Scenario Lab…</div>;
  if (result.status === "unavailable") return <div className={styles.message} role="alert"><h1>Scenario Lab is unavailable</h1><p>These walkthrough controls are only available with synthetic demo data. Real monitoring remains separate.</p><Link href="/">Return to clinic overview</Link></div>;
  if (result.status === "error") return <div className={styles.message} role="alert"><h1>Scenario Lab could not open</h1><p>{result.message}</p><Link href="/">Return to clinic overview</Link></div>;

  const { definitions, state } = result.data;
  const active = definitions.find((definition) => definition.scenarioId === state.activeScenarioId) ?? null;
  const targetHref = state.targetEventId ? `/events/${state.targetEventId}` : `/residents/${state.targetResidentId}`;
  const targetLabel = state.targetEventId ? "Open generated event" : "Open Resident A";

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div><h1>Scenario Lab</h1><p>Run a safe, synthetic situation and inspect exactly what clinic staff would see.</p></div>
        <StatusPill label={active ? `${active.label} active` : "Baseline demo"} tone={active ? toneMap[active.tone] : "healthy"} />
      </header>

      <div className={styles.boundary}>
        <strong>Frontend walkthrough only</strong>
        <p>These controls change local demo data. They do not send sensor readings, call the backend, diagnose a condition, or prove anyone is safe.</p>
      </div>

      <div className={styles.layout}>
        <section className={styles.sheet}>
          <div className={styles.sheetHeader}><div><h2>Choose the next room story</h2><p>Each scenario updates the same resident, event, and setup screens used by the rest of the app.</p></div><span>Resident A · Room 101</span></div>
          <div className={styles.scenarioList}>
            {definitions.map((definition, index) => {
              const isActive = definition.scenarioId === state.activeScenarioId;
              return (
                <article className={styles.scenarioRow} data-active={isActive} data-tone={definition.tone} key={definition.scenarioId}>
                  <span className={styles.stepNumber}>{String(index + 1).padStart(2, "0")}</span>
                  <div className={styles.scenarioCopy}>
                    <div className={styles.rowTitle}><h3>{definition.label}</h3>{isActive && <StatusPill label="Active" tone={toneMap[definition.tone]} />}</div>
                    <p>{definition.summary}</p>
                    <div className={styles.safetyRule}><strong>Safety rule</strong><span>{definition.safetyRule}</span></div>
                  </div>
                  <button type="button" disabled={running !== null || isActive} onClick={() => void runScenario(definition.scenarioId)}>{running === definition.scenarioId ? "Running…" : isActive ? "Running now" : `Run ${definition.label.toLowerCase()}`}</button>
                </article>
              );
            })}
          </div>
        </section>

        <aside className={styles.resultRail}>
          <div className={styles.resultHeader}><div><h2>{active ? `${active.label} active` : "Baseline demo"}</h2><p>{active ? "The shared clinic demo now reflects this situation." : "Resident A begins with active monitoring and no open attention items."}</p></div><span className={styles.liveDot} aria-hidden="true" /></div>
          {active ? <ol className={styles.outcomes}>{active.expectedOutcomes.map((outcome) => <li key={outcome}>{outcome}</li>)}</ol> : <div className={styles.baseline}><strong>Ready for a walkthrough</strong><p>Choose one situation. You can inspect the result, return here, and run another without changing real data.</p></div>}
          <dl className={styles.resultMeta}><div><dt>Applied</dt><dd>{formattedTime(state.appliedAt)}</dd></div><div><dt>Data</dt><dd>Synthetic and local</dd></div></dl>
          {message && <p className={styles.feedback} role="status">{message}</p>}
          {active && <Link className={styles.openLink} href={targetHref}>{targetLabel}<ArrowIcon /></Link>}
          <button className={styles.resetButton} type="button" disabled={running !== null || !active} onClick={() => void resetScenario()}>{running === "reset" ? "Resetting…" : "Reset demo"}</button>
        </aside>
      </div>
    </section>
  );
}
