"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { FacilityTimeField } from "@/components/ui/facility-time-field";
import type { MonitoringEventDetail, ResolutionOutcome } from "@/lib/monitoring";
import { hasWorkspacePermission, useWorkspace, type CheckOutcome, type WorkspaceSnapshot } from "@/lib/workspace";
import { isCareInstant, outcomeLabels } from "./care-format";
import { PermissionNotice } from "./care-shared";
import styles from "./care-workspace.module.css";

export type ResponseMode = "response" | "resolve";

export function canResolveConcern(event: MonitoringEventDetail, snapshot: WorkspaceSnapshot) {
  const latest = snapshot.checks.filter((check) => check.eventId === event.eventId).at(-1);
  return event.status === "checked" && (!latest || latest.completedCheck) &&
    !snapshot.followUps.some((followUp) => followUp.eventId === event.eventId && followUp.status !== "completed");
}

export function messageFor(cause: unknown): string {
  return cause instanceof Error
    ? cause.message
    : "The save could not be confirmed. Your entry is still here; review the current record before retrying.";
}
function newActionId() {
  return globalThis.crypto.randomUUID();
}
const outcomeHints: Partial<Record<CheckOutcome, string>> = {
  no_concern_observed:
    "Records the observation at that time; the concern stays open.",
  assistance_requested: "Records a request, not arrival of assistance.",
  unable_to_check:
    "Does not record a completed check. Follow-up remains needed.",
  information_needs_review:
    "Does not dismiss this concern or validate an assignment.",
  other: "A short explanation is required.",
};
export function EventActions({
  event,
  snapshot,
  initialMode = "response",
  onPendingChange,
  onDirtyChange,
}: {
  event: MonitoringEventDetail;
  snapshot: WorkspaceSnapshot;
  initialMode?: ResponseMode;
  onPendingChange: (pending: boolean) => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const { client, refresh } = useWorkspace();
  const [outcome, setOutcome] = useState<CheckOutcome | "">("");
  const [note, setNote] = useState("");
  const [checkedAt, setCheckedAt] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [mode, setMode] = useState<ResponseMode>(initialMode);
  const [resolutionPending, setResolutionPending] = useState(false);
  const [resolutionDirty, setResolutionDirty] = useState(false);
  const responseHeadingId = useId();
  const checkRequest = useRef<string | null>(null);
  const ackRequest = useRef<string | null>(null);
  const canResolve = canResolveConcern(event, snapshot);
  const permittedToResolve = hasWorkspacePermission(snapshot, "resolve_concern");
  const busy = pending !== null || resolutionPending;
  const currentMode = mode === "resolve" && canResolve && permittedToResolve ? "resolve" : "response";
  useEffect(() => { onPendingChange(busy); }, [busy, onPendingChange]);
  useEffect(() => {
    onDirtyChange(Boolean(outcome || note || checkedAt || resolutionDirty));
  }, [outcome, note, checkedAt, resolutionDirty, onDirtyChange]);
  useEffect(() => () => { onPendingChange(false); onDirtyChange(false); }, [onPendingChange, onDirtyChange]);
  async function acknowledge() {
    if (!hasWorkspacePermission(snapshot, "acknowledge")) {
      setError(
        "This shared device is not permitted to acknowledge concerns. Ask an administrator to review its permissions.",
      );
      return;
    }
    setPending("ack");
    setError("");
    setSaved("");
    ackRequest.current ??= newActionId();
    try {
      await client.acknowledgeEvent(event.eventId, ackRequest.current);
      await refresh();
      setSaved(
        `Acknowledged from ${snapshot.currentClient.name} in this demonstration. No resident check has been recorded by this action.`,
      );
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setPending(null);
    }
  }
  async function check(submitEvent: FormEvent) {
    submitEvent.preventDefault();
    if (!hasWorkspacePermission(snapshot, "record_check")) {
      setError(
        "This shared device is not permitted to record resident checks. Ask an administrator to review its permissions.",
      );
      return;
    }
    if (!outcome) {
      setError("Choose what happened before saving.");
      return;
    }
    if (outcome === "other" && !note.trim()) {
      setError("Add a short explanation for another outcome.");
      return;
    }
    if (checkedAt && !isCareInstant(checkedAt)) {
      setError(
        "Choose a valid facility check time, including which occurrence if the clock repeats, or leave it blank to use the save time.",
      );
      return;
    }
    setPending("check");
    setError("");
    setSaved("");
    checkRequest.current ??= newActionId();
    try {
      const record = await client.recordCheck(event.eventId, {
        outcome,
        note: note.trim(),
        ...(checkedAt ? { checkedAt } : {}),
        requestId: checkRequest.current,
      });
      await refresh();
      setSaved(
        record.completedCheck
          ? "Outcome saved in this demonstration. A check has been recorded; this concern is still open until explicitly resolved."
          : "Outcome saved in this demonstration. This was not recorded as a completed check. The concern and needed follow-up remain visible.",
      );
      setOutcome("");
      setNote("");
      setCheckedAt("");
      checkRequest.current = null;
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setPending(null);
    }
  }
  return (
    <section className={styles.popupActions} aria-labelledby={responseHeadingId}>
      <div className={styles.responseModes} role="group" aria-label="Response actions">
        <Button variant={currentMode === "response" ? "primary" : "secondary"} aria-pressed={currentMode === "response"} disabled={busy} onClick={() => setMode("response")}>
          Record response
        </Button>
        <Button variant={currentMode === "resolve" ? "primary" : "secondary"} aria-pressed={currentMode === "resolve"} disabled={busy || !canResolve || !permittedToResolve} onClick={() => setMode("resolve")}>
          Resolve concern
        </Button>
      </div>
      {!canResolve && <p className={styles.finePrint}>
        {event.status === "checked"
          ? "Resolution needs a completed check and no outstanding follow-up."
          : "Record a completed check before resolving this concern."}
      </p>}
      {!permittedToResolve && <PermissionNotice action="resolve concerns" />}
      {error && <p className={styles.actionError} role="alert">{error}</p>}
      {saved && <p className={styles.saved} role="status">{saved}</p>}
      <div hidden={currentMode !== "response"}>
      <h3 id={responseHeadingId}>Record response</h3>
      <p>
        Actions use {snapshot.currentClient.name}. Acknowledgment marks this seen; it does not confirm a responder or a completed check.
      </p>
      {event.status === "open" &&
        hasWorkspacePermission(snapshot, "acknowledge") && (
          <Button
            pending={pending === "ack"}
            disabled={busy}
            onClick={() => void acknowledge()}
            pendingLabel="Saving acknowledgment…"
          >
            Acknowledge concern
          </Button>
        )}
      {event.status === "open" &&
        !hasWorkspacePermission(snapshot, "acknowledge") && (
          <PermissionNotice action="acknowledge concerns" />
        )}
      {(event.status === "acknowledged" || event.status === "checked") &&
        !hasWorkspacePermission(snapshot, "record_check") && (
          <PermissionNotice action="record resident checks" />
        )}
      {(event.status === "acknowledged" || event.status === "checked") &&
        hasWorkspacePermission(snapshot, "record_check") && (
          <form className={styles.form} onSubmit={(e) => void check(e)}>
            <fieldset disabled={busy}>
              <legend>What happened?</legend>
              {(Object.entries(outcomeLabels) as [CheckOutcome, string][]).map(
                ([value, label]) => (
                  <label className={styles.radio} key={value}>
                    <input
                      type="radio"
                      name={`outcome-${event.eventId}`}
                      value={value}
                      checked={outcome === value}
                      onChange={() => {
                        setOutcome(value);
                        checkRequest.current = null;
                        setSaved("");
                      }}
                    />
                    <span>
                      {label}
                      {outcomeHints[value] && (
                        <small>{outcomeHints[value]}</small>
                      )}
                    </span>
                  </label>
                ),
              )}
            </fieldset>
            <FormField
              as="textarea"
              label={
                outcome === "other" ? "Short explanation" : "Note (optional)"
              }
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
                checkRequest.current = null;
              }}
              maxLength={1200}
              disabled={busy}
            />
            <details>
              <summary className={styles.meta}>
                Record a different check time
              </summary>
              <div style={{ marginTop: 12 }}>
                <FacilityTimeField
                  label="Actual check time"
                  value={checkedAt}
                  timeZone={snapshot.facility.timeZone}
                  onChange={(value) => {
                    setCheckedAt(value);
                    checkRequest.current = null;
                  }}
                  hint="Optional. An earlier time is recorded as staff-reported; it does not rewrite earlier actions."
                  disabled={busy}
                />
              </div>
            </details>
            <Button
              type="submit"
              pending={pending === "check"}
              disabled={busy}
              pendingLabel="Saving outcome…"
            >
              Save outcome
            </Button>
            <p className={styles.finePrint}>
              Saving an outcome does not automatically resolve a concern.
            </p>
          </form>
        )}
      {event.status === "detected" && (
        <p>
          Analysis is pending. No response action is available from the current
          event record. Follow the facility procedure if help is needed.
        </p>
      )}
      </div>
      <div hidden={currentMode !== "resolve"}>
        <ResolutionForm eventId={event.eventId} onPendingChange={setResolutionPending} onDirtyChange={setResolutionDirty} />
      </div>
    </section>
  );
}
function ResolutionForm({ eventId, onPendingChange, onDirtyChange }: {
  eventId: string;
  onPendingChange: (pending: boolean) => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const { client, refresh, snapshot } = useWorkspace();
  const [outcome, setOutcome] = useState<ResolutionOutcome | "">("");
  const [label, setLabel] = useState("");
  const [routine, setRoutine] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<string | null>(null);
  useEffect(() => { onPendingChange(pending); }, [pending, onPendingChange]);
  useEffect(() => { onDirtyChange(Boolean(outcome || label || routine)); }, [outcome, label, routine, onDirtyChange]);
  useEffect(() => () => { onPendingChange(false); onDirtyChange(false); }, [onPendingChange, onDirtyChange]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!hasWorkspacePermission(snapshot, "resolve_concern")) {
      setError(
        "This shared device is not permitted to resolve concerns. Ask an administrator to review its permissions.",
      );
      return;
    }
    const currentEvent = snapshot?.events.find((item) => item.eventId === eventId);
    if (!snapshot || !currentEvent || !canResolveConcern(currentEvent, snapshot)) {
      setError("This concern needs a completed check and no outstanding follow-up before it can be resolved. Your entry is still here.");
      return;
    }
    if (!outcome || !label.trim() || !routine) {
      setError(
        "Choose a supported outcome, describe what happened and say whether it was a usual routine.",
      );
      return;
    }
    setPending(true);
    setError("");
    request.current ??= newActionId();
    try {
      await client.resolveEvent(eventId, {
        outcome,
        actualEventLabel: label.trim(),
        routine: routine === "yes",
        requestId: request.current,
      });
      await refresh();
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setPending(false);
    }
  }
  return (
    <section aria-label="Explicit resolution">
      <h3>Resolve this concern</h3>
      <form
        className={styles.form}
        onSubmit={(e) => void submit(e)}
        style={{ marginTop: 16 }}
      >
        <p className={styles.finePrint}>
          This explicitly closes the concern and preserves its history. A later
          recurrence is separate work.
        </p>
        <FormField
          as="select"
          label="Resolution outcome"
          disabled={pending}
          value={outcome}
          onChange={(e) => {
            setOutcome(e.target.value as ResolutionOutcome);
            request.current = null;
          }}
          options={[
            { value: "", label: "Choose an outcome" },
            { value: "confirmed", label: "Concern confirmed" },
            { value: "false_positive", label: "Reported as a false concern" },
            { value: "uncertain", label: "Cause remains uncertain" },
          ]}
        />
        <FormField
          as="textarea"
          label="What actually happened?"
          disabled={pending}
          value={label}
          onChange={(e) => {
            setLabel(e.target.value);
            request.current = null;
          }}
          maxLength={800}
        />
        <FormField
          as="select"
          label="Was this a usual routine?"
          disabled={pending}
          value={routine}
          onChange={(e) => {
            setRoutine(e.target.value);
            request.current = null;
          }}
          options={[
            { value: "", label: "Choose an answer" },
            { value: "yes", label: "Yes" },
            { value: "no", label: "No" },
          ]}
        />
        <Button variant="secondary" type="submit" pending={pending}>
          Confirm resolution
        </Button>
        {error && (
          <p role="alert" className={styles.actionError}>
            {error}
          </p>
        )}
      </form>
    </section>
  );
}
