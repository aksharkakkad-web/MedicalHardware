import { useId, type ReactNode } from "react";

import styles from "./system-state.module.css";

export const SYSTEM_STATE_KEYS = [
  "calibrating",
  "partial_baseline",
  "resident_away",
  "resident_returned",
  "possible_multi_person",
  "device_degraded",
  "device_offline",
  "buffering",
  "retrying",
  "missing_assignment",
  "unknown_anomaly",
  "ai_interpretation_pending",
  "ai_interpretation_unavailable",
  "loading",
  "genuine_empty",
  "filtered_empty",
  "stale_data",
  "save_failure",
  "conflicting_update",
  "overdue_work",
  "resolved_read_only",
  "recurrence_new_linked_event",
] as const;

export type SystemStateKey = (typeof SYSTEM_STATE_KEYS)[number];
export type SystemStateSemantic =
  | "positive"
  | "info"
  | "caution"
  | "risk"
  | "limited"
  | "neutral";

export type SystemStateCategory =
  | "monitoring"
  | "device"
  | "transport"
  | "assignment"
  | "anomaly"
  | "interpretation"
  | "feedback"
  | "workflow";

export type SystemStateDefinition = Readonly<{
  title: string;
  category: SystemStateCategory;
  provenance: string;
  semantic: SystemStateSemantic;
  known: string;
  limited: string;
  whyItMatters: string;
  nextAction: string;
}>;

type CompleteSystemStateCatalog = {
  [Key in SystemStateKey]: SystemStateDefinition;
};

// Keep this record complete: adding a key without documenting all four facts is a type error.
export const SYSTEM_STATE_CATALOG = {
  calibrating: {
    title: "Calibrating",
    category: "monitoring",
    provenance: "Setup and baseline state",
    semantic: "info",
    known: "The room setup is settling and calibration work is in progress.",
    limited: "Resident-specific output may be limited; an established baseline is not ready yet.",
    whyItMatters: "Early readings should not be treated as a stable picture of this resident's routine.",
    nextAction: "Wait for calibration to complete, then review the resulting baseline status.",
  },
  partial_baseline: {
    title: "Partial baseline",
    category: "monitoring",
    provenance: "Resident baseline state",
    semantic: "caution",
    known: "Some resident-specific baseline dimensions have been established.",
    limited: "Other dimensions do not have enough eligible history for a complete comparison.",
    whyItMatters: "An anomaly comparison may be less informative while the baseline is partial.",
    nextAction: "Use the available evidence cautiously and allow eligible monitoring history to accumulate.",
  },
  resident_away: {
    title: "Resident away",
    category: "monitoring",
    provenance: "Occupancy and monitoring state",
    semantic: "limited",
    known: "The resident-away state is active for the assigned room.",
    limited: "Resident-specific monitoring is paused while the resident is away.",
    whyItMatters: "Resident-specific baseline learning is paused so absence is not learned as normal behavior.",
    nextAction: "Confirm the coverage context when needed and wait for a return transition before resident-specific review.",
  },
  resident_returned: {
    title: "Resident returned / return transition",
    category: "monitoring",
    provenance: "Occupancy transition",
    semantic: "info",
    known: "The room has a new return transition after an away period.",
    limited: "A return does not by itself prove that the resident is safe or that all resident-specific evidence is current.",
    whyItMatters: "Returning is an awareness update, not a clinical conclusion; learning resumes only when eligible.",
    nextAction: "Review current evidence and let the monitoring state settle before making a resident-specific decision.",
  },
  possible_multi_person: {
    title: "Possible multi-person presence",
    category: "monitoring",
    provenance: "Occupancy ambiguity state",
    semantic: "limited",
    known: "Room telemetry suggests that more than one person may be present.",
    limited: "Resident-specific attribution is unavailable; do not guess which person caused a signal.",
    whyItMatters: "Resident-specific baseline learning is paused while attribution is ambiguous.",
    nextAction: "Confirm occupancy context before using resident-specific output or recording a resident-specific conclusion.",
  },
  device_degraded: {
    title: "Device degraded",
    category: "device",
    provenance: "Device-health state",
    semantic: "caution",
    known: "The room device is reporting, but one or more sources may be limited.",
    limited: "Some current sensor evidence may be missing or lower quality.",
    whyItMatters: "Device health is separate from resident attention; limited sources can reduce confidence without creating a resident conclusion.",
    nextAction: "Review device and source health, then use only the evidence that is currently available.",
  },
  device_offline: {
    title: "Device offline",
    category: "device",
    provenance: "Device-health state",
    semantic: "limited",
    known: "The room unit is not currently reporting to the monitoring service.",
    limited: "Current room and resident-specific evidence is unavailable until reporting resumes.",
    whyItMatters: "Device health is separate from resident attention; an offline unit is not evidence that the resident is safe or unsafe.",
    nextAction: "Check the room unit's connection and follow the device recovery procedure.",
  },
  buffering: {
    title: "Buffering",
    category: "transport",
    provenance: "Edge transport state",
    semantic: "caution",
    known: "The edge unit is holding compact telemetry while upload is unavailable or delayed.",
    limited: "The held telemetry is not current evidence; the interface does not fabricate current data.",
    whyItMatters: "A growing transport delay can make resident-specific output stale even when the device is powered.",
    nextAction: "Review connection health and wait for confirmed ingestion before treating a reading as current.",
  },
  retrying: {
    title: "Retrying",
    category: "transport",
    provenance: "Transport recovery state",
    semantic: "caution",
    known: "A failed upload or operation is being attempted again.",
    limited: "Current data may be delayed; retrying does not fabricate current data or confirm success.",
    whyItMatters: "The next decision should use confirmed evidence, not an assumed successful retry.",
    nextAction: "Allow the retry to finish, then verify the last confirmed update before acting.",
  },
  missing_assignment: {
    title: "Missing room/resident assignment",
    category: "assignment",
    provenance: "Room and resident configuration",
    semantic: "limited",
    known: "The device or room does not have a complete authorized resident assignment.",
    limited: "Resident-specific attribution and resident baseline comparisons are unavailable.",
    whyItMatters: "Room telemetry must not be presented as belonging to a resident without an authorized assignment.",
    nextAction: "Complete or verify the room and resident assignment before using resident-specific output.",
  },
  unknown_anomaly: {
    title: "Unknown anomaly",
    category: "anomaly",
    provenance: "Deterministic anomaly output",
    semantic: "caution",
    known: "A meaningful deviation was detected, but it does not match a supported event family.",
    limited: "The system cannot name a cause from this evidence and makes no diagnosis.",
    whyItMatters: "Keeping an unknown anomaly general avoids forcing uncertain evidence into a misleading label.",
    nextAction: "Review the structured evidence and observed context; record what staff can verify.",
  },
  ai_interpretation_pending: {
    title: "AI interpretation pending",
    category: "interpretation",
    provenance: "AI interpretation stage",
    semantic: "info",
    known: "A structured evidence packet is awaiting an optional plain-language interpretation.",
    limited: "The interpretation is not ready; the deterministic warning remains visible and actionable.",
    whyItMatters: "AI adds context after evidence exists; it does not monitor telemetry or decide whether a warning is real.",
    nextAction: "Review the deterministic evidence now and wait for interpretation only if additional context is useful.",
  },
  ai_interpretation_unavailable: {
    title: "AI interpretation unavailable",
    category: "interpretation",
    provenance: "AI interpretation stage",
    semantic: "limited",
    known: "The deterministic evidence and warning decision remain available.",
    limited: "The optional AI interpretation is unavailable; it is never a diagnosis.",
    whyItMatters: "The deterministic warning remains visible and actionable; a missing interpretation cannot suppress it or remove the work item.",
    nextAction: "Review the deterministic warning and structured evidence; continue the workflow without AI interpretation.",
  },
  loading: {
    title: "Loading",
    category: "feedback",
    provenance: "Interface feedback state",
    semantic: "info",
    known: "The requested operational content has not finished loading.",
    limited: "Loading state; current operational details are not available yet.",
    whyItMatters: "A placeholder must not look like a current reading or an empty result.",
    nextAction: "Wait for the request to complete before making an operational decision.",
  },
  genuine_empty: {
    title: "Genuine empty",
    category: "feedback",
    provenance: "Operational collection state",
    semantic: "neutral",
    known: "No items match the requested collection because there are genuinely none to show.",
    limited: "Nothing is unavailable for this empty collection; monitoring continues where configured.",
    whyItMatters: "An explicit empty result prevents staff from mistaking a clear queue for a loading or error state.",
    nextAction: "Continue to the next review area or wait for new work to arrive.",
  },
  filtered_empty: {
    title: "Filtered empty",
    category: "feedback",
    provenance: "Collection and filter state",
    semantic: "neutral",
    known: "The collection has content, but the active filters match no items.",
    limited: "Items outside the active filter are not shown in this view.",
    whyItMatters: "A filtered empty result is different from a genuinely empty collection.",
    nextAction: "Review or clear the filters to see the available collection.",
  },
  stale_data: {
    title: "Stale data",
    category: "feedback",
    provenance: "Evidence freshness state",
    semantic: "limited",
    known: "A last-known update exists, but it is no longer current.",
    limited: "The current resident or device condition is unavailable; last-known values are not live.",
    whyItMatters: "Stale evidence can change the priority of a decision and must not be shown with fake precision.",
    nextAction: "Refresh or check the transport and device state before relying on the last-known value.",
  },
  save_failure: {
    title: "Save failure",
    category: "feedback",
    provenance: "User action result",
    semantic: "risk",
    known: "The requested change was not confirmed as saved.",
    limited: "The record may still contain its previous value; the local change is not confirmed.",
    whyItMatters: "Unconfirmed workflow changes must not be presented as completed care documentation.",
    nextAction: "Retry the save and verify the confirmation before leaving this workflow.",
  },
  conflicting_update: {
    title: "Conflicting update",
    category: "feedback",
    provenance: "Concurrent update protection",
    semantic: "caution",
    known: "Another update changed the record before this change could be applied.",
    limited: "The local change was not applied, and the current record needs to be reloaded.",
    whyItMatters: "Conflict recovery prevents one person's newer observation from being silently overwritten.",
    nextAction: "Reload the current record, compare the changes, and reapply only what is still correct.",
  },
  overdue_work: {
    title: "Overdue work",
    category: "workflow",
    provenance: "Care workflow state",
    semantic: "risk",
    known: "An open work item passed its expected follow-up time.",
    limited: "The item remains open until an authorized workflow action resolves it.",
    whyItMatters: "High and critical events never silently expire; overdue status needs explicit follow-up.",
    nextAction: "Review the available evidence and continue, escalate, or resolve through the documented workflow.",
  },
  resolved_read_only: {
    title: "Resolved read-only",
    category: "workflow",
    provenance: "Immutable event history",
    semantic: "positive",
    known: "The work item has a recorded resolution and is shown as history.",
    limited: "Resolved history cannot be edited or reopened in place.",
    whyItMatters: "Resolved history remains immutable so the record preserves what happened and when.",
    nextAction: "Review the recorded outcome; create a new linked event if the same concern occurs again.",
  },
  recurrence_new_linked_event: {
    title: "Recurrence / new linked event",
    category: "workflow",
    provenance: "Event relationship and workflow state",
    semantic: "caution",
    known: "A new event is linked to an earlier resolved event as a recurrence.",
    limited: "The earlier resolved event remains read-only and is not reopened.",
    whyItMatters: "A new linked event preserves separate timelines, ownership, and evidence for each occurrence.",
    nextAction: "Review the new event as current work while using the linked history for context.",
  },
} satisfies CompleteSystemStateCatalog;

export type SystemStateAction =
  | Readonly<{ kind: "retry_save"; onClick: () => void }>
  | Readonly<{ kind: "reload_record"; onClick: () => void }>
  | Readonly<{ kind: "check_device"; onClick: () => void }>;

type SharedSystemStateProps = Readonly<{
  className?: string;
  idPrefix?: string;
}>;

type NonActionableSystemStateProps = SharedSystemStateProps & Readonly<{
  state: Exclude<SystemStateKey, "save_failure" | "conflicting_update" | "device_offline">;
  action?: never;
}>;

type ActionableSystemStateProps = SharedSystemStateProps & (
  | Readonly<{ state: "save_failure"; action?: Extract<SystemStateAction, { kind: "retry_save" }> }>
  | Readonly<{ state: "conflicting_update"; action?: Extract<SystemStateAction, { kind: "reload_record" }> }>
  | Readonly<{ state: "device_offline"; action?: Extract<SystemStateAction, { kind: "check_device" }> }>
);

export type SystemStateProps = NonActionableSystemStateProps | ActionableSystemStateProps;

function Fact({ label, children }: Readonly<{ label: string; children: ReactNode }>) {
  return (
    <div className={styles.fact}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function SystemState({ state, action, className, idPrefix = "system-state" }: SystemStateProps) {
  const definition = SYSTEM_STATE_CATALOG[state];
  const instanceId = useId();
  const headingId = `${idPrefix}-${state}-${instanceId.replaceAll(":", "")}`;
  const classes = [styles.state, className].filter(Boolean).join(" ");

  const safeAction = (() => {
    if (!action) return null;

    if (state === "save_failure" && action.kind === "retry_save" && typeof action.onClick === "function") {
      return { label: "Retry save", onClick: action.onClick };
    }
    if (state === "conflicting_update" && action.kind === "reload_record" && typeof action.onClick === "function") {
      return { label: "Reload record", onClick: action.onClick };
    }
    if (state === "device_offline" && action.kind === "check_device" && typeof action.onClick === "function") {
      return { label: "Check device connection", onClick: action.onClick };
    }

    // Runtime callers can still bypass TypeScript, so never render an action
    // that is not explicitly allowed for this state.
    return null;
  })();

  return (
    <article
      className={classes}
      data-system-state={state}
      data-semantic={definition.semantic}
      aria-labelledby={headingId}
    >
      <header className={styles.header}>
        <div>
          <p className={styles.category}>{definition.category}</p>
          <h3 id={headingId}>{definition.title}</h3>
        </div>
        <span className={styles.semantic} data-semantic-label={definition.semantic}>
          {definition.semantic}
        </span>
      </header>
      <p className={styles.provenance}>Provenance: {definition.provenance}</p>
      <dl className={styles.facts}>
        <Fact label="What is known">{definition.known}</Fact>
        <Fact label="What is unavailable or limited">{definition.limited}</Fact>
        <Fact label="Why it matters">{definition.whyItMatters}</Fact>
      </dl>
      <div className={styles.nextAction}>
        <span>Allowed next action</span>
        <p>{definition.nextAction}</p>
        {safeAction ? (
          <button type="button" onClick={safeAction.onClick}>{safeAction.label}</button>
        ) : null}
      </div>
      {state === "loading" ? (
        <div className={styles.skeleton} data-testid="system-state-loading-skeleton" aria-hidden="true">
          <span /><span /><span />
        </div>
      ) : null}
    </article>
  );
}

export type SystemStateCatalogProps = Readonly<{
  states?: readonly SystemStateKey[];
  className?: string;
  idPrefix?: string;
}>;

export function SystemStateCatalog({ states = SYSTEM_STATE_KEYS, className, idPrefix = "system-state-catalog" }: SystemStateCatalogProps) {
  return (
    <div className={[styles.catalog, className].filter(Boolean).join(" ")}>
      {states.map((state) => <SystemState key={state} state={state} idPrefix={idPrefix} />)}
    </div>
  );
}

const lifecycleStates = [
  {
    key: "new",
    title: "Open · new",
    copy: "A new work item is ready for evidence review.",
    next: "Review the available evidence before acknowledging or investigating.",
  },
  {
    key: "acknowledged",
    title: "Acknowledged",
    copy: "The work item is seen and remains open for follow-up.",
    next: "Continue with the documented check; acknowledgement does not resolve the item.",
  },
  {
    key: "investigating",
    title: "Investigating",
    copy: "Staff are checking the evidence and observed context.",
    next: "Keep the item open until the check has a recorded outcome.",
  },
  {
    key: "overdue",
    title: "Overdue",
    copy: "Expected follow-up time passed while the item remained open.",
    next: "Take explicit follow-up action; high and critical events never silently expire.",
  },
  {
    key: "resolved",
    title: "Resolved read-only",
    copy: "The event has a recorded outcome and remains immutable history.",
    next: "Read the outcome; never reopen resolved history in place.",
  },
  {
    key: "recurrence",
    title: "Recurrence / new linked event",
    copy: "A new event links to the earlier resolved event for context.",
    next: "Work the new event as current work while preserving the prior event unchanged.",
  },
] as const;

export function SystemLifecycle() {
  return (
    <section className={styles.lifecycle} aria-labelledby="system-event-lifecycle">
      <header>
        <p className={styles.sectionLabel}>Workflow specimen · synthetic/test-only</p>
        <h3 id="system-event-lifecycle">Event lifecycle</h3>
        <p>Open work progresses explicitly. Resolved history is immutable; a recurrence is a new linked event.</p>
      </header>
      <ol>
        {lifecycleStates.map((item) => (
          <li key={item.key} data-lifecycle-state={item.key}>
            <span className={styles.lifecycleStep}>{String(lifecycleStates.indexOf(item) + 1).padStart(2, "0")}</span>
            <div>
              <h4>{item.title}</h4>
              <p>{item.copy}</p>
              <small>{item.next}</small>
            </div>
          </li>
        ))}
      </ol>
      <p className={styles.lifecycleNote}>Watch items may auto-close into history only when that behavior is documented; high and critical events never silently expire.</p>
    </section>
  );
}

const feedbackStates: readonly SystemStateKey[] = [
  "loading",
  "genuine_empty",
  "filtered_empty",
  "stale_data",
  "save_failure",
  "conflicting_update",
];

export function SystemFeedback() {
  return (
    <section className={styles.feedback} aria-labelledby="system-feedback">
      <header>
        <p className={styles.sectionLabel}>Interface feedback · synthetic/test-only</p>
        <h3 id="system-feedback">System feedback</h3>
        <p>Skeleton loading, genuine empty, filtered empty, stale refresh, retryable save failure, and conflict recovery explain whether content is loading, absent, old, or needs recovery.</p>
      </header>
      <div className={styles.feedbackGrid}>
        {feedbackStates.map((state) => <SystemState key={state} state={state} idPrefix="system-feedback-state" />)}
      </div>
    </section>
  );
}

export const systemStateCatalog = SYSTEM_STATE_CATALOG;
export const systemStateKeys = SYSTEM_STATE_KEYS;
