"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ChevronLeftIcon } from "@/components/icons/icons";
import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import {
  useMonitoringClient,
  type CalibrationDimensionId,
  type ResidentMonitoringSetupResponse,
  type SetupChangeInput,
  type SetupChangeReason,
} from "@/lib/monitoring";

import styles from "./monitoring-setup.module.css";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; data: ResidentMonitoringSetupResponse };

const setupTone: Record<ResidentMonitoringSetupResponse["setup"]["status"], StatusTone> = {
  new: "neutral",
  calibrating: "attention",
  partial: "attention",
  established: "healthy",
};

const dimensionLabel: Record<CalibrationDimensionId, string> = {
  movement: "Movement patterns",
  respiratory_rate: "Breathing-rate patterns",
};

const reasonOptions: Array<{ value: SetupChangeReason; label: string }> = [
  { value: "device_moved", label: "The device moved" },
  { value: "room_layout_changed", label: "The room layout changed" },
  { value: "core_sensor_replaced", label: "A core sensor was replaced" },
  { value: "resident_moved", label: "The resident moved rooms" },
];

const setupReasonLabel: Record<SetupChangeReason, string> = Object.fromEntries(
  reasonOptions.map((option) => [option.value, option.label]),
) as Record<SetupChangeReason, string>;

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function humanize(value: string): string {
  return value.replaceAll("_", " ");
}

export function MonitoringSetup({ residentId }: Readonly<{ residentId: string }>) {
  const client = useMonitoringClient();
  const [result, setResult] = useState<LoadState>({ status: "loading" });
  const [reason, setReason] = useState<SetupChangeReason>("device_moved");
  const [selected, setSelected] = useState<CalibrationDimensionId[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    client.getResidentMonitoringSetup(residentId)
      .then((data) => { if (current) setResult({ status: "success", data }); })
      .catch(() => { if (current) setResult({ status: "error" }); });
    return () => { current = false; };
  }, [client, residentId]);

  async function recordChange(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selected.length === 0) {
      setMessage("Choose at least one calibration area.");
      return;
    }
    setIsSaving(true);
    setMessage(null);
    if (result.status !== "success") return;
    const input: SetupChangeInput = {
      reason,
      affectedDimensions: selected,
      expectedCalibrationVersion: result.data.setup.version,
    };
    try {
      const data = await client.recordSetupChange(residentId, input);
      setResult({ status: "success", data });
      setSelected([]);
      setMessage("Setup change saved. Only the selected areas restarted calibration.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The setup change could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  if (result.status === "loading") return <div className={styles.message} role="status">Opening monitoring setup…</div>;
  if (result.status === "error") return <div className={styles.message} role="alert"><h1>Monitoring setup is unavailable</h1><p>This screen cannot confirm assignment or calibration readiness.</p><Link href={`/residents/${residentId}`}>Return to resident</Link></div>;

  const { setup } = result.data;
  const assignmentReady = setup.assignmentStatus === "valid";
  const deviceReady = assignmentReady && setup.deviceStatus !== "offline" && setup.deviceStatus !== "unknown";
  const collectionPaused = setup.learningState !== "active";
  const calibrationReady = setup.status === "established";
  const canRecordChange = assignmentReady && setup.deviceId !== null;
  const readiness = [
    { label: "Room assignment", ready: assignmentReady, detail: assignmentReady ? `${setup.residentLabel} is linked to ${setup.roomLabel}.` : "An authorized administrator must resolve the assignment." },
    { label: "Room device", ready: deviceReady, detail: deviceReady ? `${setup.deviceLabel} is available for setup.` : setup.deviceStatus === "offline" ? "The room device is offline." : "A usable device assignment is not available." },
    { label: "Clean learning period", ready: !collectionPaused && deviceReady, detail: setup.learningReason },
    { label: "Calibration", ready: calibrationReady, detail: setup.status === "partial" ? "Some areas are ready while others recalibrate." : setup.status === "established" ? "All demo calibration areas are established." : "Calibration is not fully ready yet." },
  ];

  return (
    <section className={styles.page}>
      <Link className={styles.back} href={`/residents/${residentId}`}><ChevronLeftIcon />{setup.residentLabel}</Link>
      <header className={styles.header}>
        <div><p>Monitoring setup</p><h1>{setup.roomLabel ?? "Assignment review"}</h1><span>{setup.residentLabel} · {setup.deviceLabel ?? "No device available"}</span></div>
        <StatusPill label={humanize(setup.status)} tone={setupTone[setup.status]} />
      </header>

      <div className={styles.demoNotice}><strong>Synthetic demo only</strong><p>These calibration states explain product behavior. They are not clinical thresholds or proof that a resident is safe.</p></div>

      <div className={styles.layout}>
        <div className={styles.mainColumn}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><span>Current calibration</span><h2>What the system can learn from this setup</h2><p>{setup.reason}</p></div><small>Version {setup.version || "not started"}</small></div>
            <div className={styles.dimensions}>
              {setup.dimensions.map((dimension) => (
                <article key={dimension.dimension}>
                  <div><strong>{dimensionLabel[dimension.dimension]}</strong><p>{dimension.status === "established" ? "This area can use its established demo baseline." : dimension.status === "partial" ? "This area has some usable history and is still learning." : dimension.status === "calibrating" ? "This area is collecting fresh clean data." : "This area has not started calibration yet."}</p></div>
                  <div className={styles.dimensionState}><StatusPill label={humanize(dimension.status)} tone={dimension.status === "established" ? "healthy" : dimension.status === "new" ? "neutral" : "attention"} /><small>{dimension.eligibleWindows} usable · {dimension.excludedWindows} excluded</small></div>
                </article>
              ))}
            </div>
          </section>

          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><span>Readiness checklist</span><h2>What this demo checks before monitoring starts</h2></div><small>{readiness.filter((item) => item.ready).length} of {readiness.length} ready</small></div>
            <ol className={styles.checklist}>
              {readiness.map((item) => <li key={item.label} data-ready={item.ready}><span aria-hidden="true">{item.ready ? "✓" : "!"}</span><div><strong>{item.label}</strong><p>{item.detail}</p></div></li>)}
            </ol>
          </section>

          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><span>Setup history</span><h2>What changed and what was preserved</h2></div><small>{setup.setupChanges.length} {setup.setupChanges.length === 1 ? "change" : "changes"}</small></div>
            {setup.setupChanges.length ? <div className={styles.history}>{[...setup.setupChanges].reverse().map((change) => <article key={`${change.newSetupVersion}-${change.changedAt}`}><span>{formatTime(change.changedAt)}</span><div><strong>{setupReasonLabel[change.reason]}</strong><p>Restarted {change.affectedDimensions.map((item) => dimensionLabel[item]).join(" and ").toLowerCase()}. Other established areas stayed intact.</p></div><small>{change.previousSetupVersion} → {change.newSetupVersion}</small></article>)}</div> : <p className={styles.empty}>No setup changes have been recorded. The original setup history is intact.</p>}
          </section>
        </div>

        <aside className={styles.sidebar}>
          <section className={styles.assignment} data-valid={assignmentReady}>
            <span>Assignment check</span><h2>{assignmentReady ? "One resident, one room" : "Assignment needs administrator help"}</h2><p>{assignmentReady ? `${setup.residentLabel} is linked to ${setup.roomLabel} and ${setup.deviceLabel}.` : setup.reason}</p>
            <dl><div><dt>Resident</dt><dd>{setup.residentLabel}</dd></div><div><dt>Room</dt><dd>{setup.roomLabel ?? "Conflict"}</dd></div><div><dt>Device</dt><dd>{setup.deviceLabel ?? "Unavailable"}</dd></div></dl>
          </section>

          <section className={styles.formPanel}>
            <span>Record a setup change</span><h2>Restart only what changed</h2><p>A device move or room change can make old patterns less useful. This demo preserves all untouched areas.</p>
            <form onSubmit={(event) => void recordChange(event)}>
              <label>What changed?<select value={reason} onChange={(event) => setReason(event.target.value as SetupChangeReason)} disabled={!canRecordChange}>{reasonOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select></label>
              <fieldset disabled={!canRecordChange}><legend>Which areas are affected?</legend>{setup.dimensions.map((dimension) => <label className={styles.checkOption} key={dimension.dimension}><input type="checkbox" checked={selected.includes(dimension.dimension)} onChange={() => setSelected((current) => current.includes(dimension.dimension) ? current.filter((item) => item !== dimension.dimension) : [...current, dimension.dimension])} /><span>{dimensionLabel[dimension.dimension]}</span></label>)}</fieldset>
              {!canRecordChange && <p className={styles.blocked}>Setup changes are locked until an authorized administrator resolves the assignment.</p>}
              {message && <p className={styles.formMessage} data-success={message.startsWith("Setup change saved")} role="status">{message}</p>}
              <button type="submit" disabled={!canRecordChange || isSaving}>{isSaving ? "Saving change…" : "Save and restart selected areas"}</button>
            </form>
          </section>
        </aside>
      </div>
    </section>
  );
}
