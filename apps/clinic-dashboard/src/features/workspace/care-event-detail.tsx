"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { FacilityTimeField } from "@/components/ui/facility-time-field";
import type {
  MonitoringEventDetail,
  ResolutionOutcome,
} from "@/lib/monitoring";
import {
  hasWorkspacePermission,
  useWorkspace,
  type CheckOutcome,
  type WorkspaceSnapshot,
} from "@/lib/workspace";
import {
  careTime,
  isCareInstant,
  eventStateLabels,
  outcomeLabels,
  residentName,
} from "./care-format";
import {
  CompletedFollowUpHistory,
  FollowUpList,
  PageHeading,
  PermissionNotice,
  WorkspaceState,
} from "./care-shared";
import styles from "./care-workspace.module.css";

function messageFor(cause: unknown): string {
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
function EventActions({
  event,
  snapshot,
}: {
  event: MonitoringEventDetail;
  snapshot: WorkspaceSnapshot;
}) {
  const { client, refresh } = useWorkspace();
  const [outcome, setOutcome] = useState<CheckOutcome | "">("");
  const [note, setNote] = useState("");
  const [checkedAt, setCheckedAt] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const checkRequest = useRef<string | null>(null);
  const ackRequest = useRef<string | null>(null);
  const checks = snapshot.checks.filter((c) => c.eventId === event.eventId);
  const latest = checks[checks.length - 1];
  const openFollowUps = snapshot.followUps.filter(
    (f) => f.eventId === event.eventId && f.status !== "completed",
  );
  const canResolve =
    event.status === "checked" &&
    (!latest || latest.completedCheck) &&
    openFollowUps.length === 0;
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
    <section className={styles.actionPanel} aria-labelledby="response-heading">
      <h2 id="response-heading">Response & outcome</h2>
      <p>
        Actions are attributed to {snapshot.currentClient.name}. Acknowledgment
        means this concern was seen; it does not verify who is responding or
        that a resident was checked.
      </p>
      {event.status === "open" &&
        hasWorkspacePermission(snapshot, "acknowledge") && (
          <Button
            pending={pending === "ack"}
            disabled={pending !== null}
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
            <fieldset disabled={pending !== null}>
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
              disabled={pending !== null}
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
                  disabled={pending !== null}
                />
              </div>
            </details>
            <Button
              type="submit"
              pending={pending === "check"}
              disabled={pending !== null}
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
      {error && (
        <p className={styles.actionError} role="alert">
          {error}
        </p>
      )}
      {saved && (
        <p className={styles.saved} role="status">
          {saved}
        </p>
      )}
      {canResolve ? (
        <>
          <hr className={styles.divider} />
          {hasWorkspacePermission(snapshot, "resolve_concern") ? (
            <ResolutionForm eventId={event.eventId} />
          ) : (
            <PermissionNotice action="resolve concerns" />
          )}
        </>
      ) : (
        event.status === "checked" && (
          <p className={styles.finePrint}>
            Resolution is not available while an incomplete check or outstanding
            follow-up needs attention.
          </p>
        )
      )}
    </section>
  );
}
function ResolutionForm({ eventId }: { eventId: string }) {
  const { client, refresh, snapshot } = useWorkspace();
  const [outcome, setOutcome] = useState<ResolutionOutcome | "">("");
  const [label, setLabel] = useState("");
  const [routine, setRoutine] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const request = useRef<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!hasWorkspacePermission(snapshot, "resolve_concern")) {
      setError(
        "This shared device is not permitted to resolve concerns. Ask an administrator to review its permissions.",
      );
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
    <details>
      <summary>Resolve this concern</summary>
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
          Resolve concern
        </Button>
        {error && (
          <p role="alert" className={styles.actionError}>
            {error}
          </p>
        )}
      </form>
    </details>
  );
}
function FollowUpEditor({
  event,
  timeZone,
}: {
  event: MonitoringEventDetail;
  timeZone: string;
}) {
  const { client, refresh, snapshot } = useWorkspace();
  const [text, setText] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  async function submit(form: FormEvent) {
    form.preventDefault();
    if (!hasWorkspacePermission(snapshot, "add_follow_up")) {
      setError(
        "This shared device is not permitted to add follow-up. Ask an administrator to review its permissions.",
      );
      return;
    }
    if (!text.trim()) {
      setError("Describe what remains to be done.");
      return;
    }
    if (dueAt && !isCareInstant(dueAt)) {
      setError(
        "Choose a valid facility due time, including which occurrence if the clock repeats, or leave it blank.",
      );
      return;
    }
    setPending(true);
    setError("");
    setSaved("");
    try {
      await client.addFollowUp({
        residentId: event.resident.residentId,
        eventId: event.eventId,
        text: text.trim(),
        ...(dueAt ? { dueAt } : {}),
      });
      await refresh();
      setText("");
      setDueAt("");
      setSaved(
        dueAt
          ? "Follow-up and due time saved in this demonstration. A responsible team has not been assigned."
          : "Follow-up saved in this demonstration. No responsible team or due time was supplied.",
      );
    } catch (cause) {
      setError(messageFor(cause));
    } finally {
      setPending(false);
    }
  }
  if (!hasWorkspacePermission(snapshot, "add_follow_up"))
    return <PermissionNotice action="add follow-up" />;
  return (
    <details style={{ marginTop: 18 }}>
      <summary>Add follow-up</summary>
      <form
        className={styles.form}
        onSubmit={(e) => void submit(e)}
        style={{ marginTop: 12 }}
      >
        <FormField
          label="What needs to happen next?"
          disabled={pending}
          as="textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={800}
        />
        <FacilityTimeField
          label="Follow-up due time (optional)"
          value={dueAt}
          onChange={setDueAt}
          timeZone={timeZone}
          disabled={pending}
        />
        <p className={styles.finePrint}>
          A responsible team has not been assigned. Use the facility’s handover
          procedure to confirm responsibility.
        </p>
        <Button variant="secondary" type="submit" pending={pending}>
          Save follow-up
        </Button>
        {error && (
          <p role="alert" className={styles.actionError}>
            {error}
          </p>
        )}
        {saved && (
          <p role="status" className={styles.saved}>
            {saved}
          </p>
        )}
      </form>
    </details>
  );
}
export function CareEventDetail({ eventId }: { eventId: string }) {
  const { snapshot, status } = useWorkspace();
  if (!snapshot || status === "error")
    return <WorkspaceState subject="Concern information" />;
  const event = snapshot.events.find((e) => e.eventId === eventId);
  if (!event) return <WorkspaceState subject="Concern information" />;
  const checks = snapshot.checks.filter((c) => c.eventId === eventId);
  const followUps = snapshot.followUps.filter(
    (f) => f.eventId === eventId && f.status !== "completed",
  );
  return (
    <div className={styles.page}>
      <Link className={styles.backLink} href="/events">
        ← Concerns
      </Link>
      <PageHeading
        title={event.headline}
        eyebrow={`${event.resident.roomLabel} · ${residentName(snapshot.profiles, event.resident.residentId, event.resident.displayLabel)}`}
        description={`Opened ${careTime(event.createdAt, snapshot.facility.timeZone)}`}
      >
        <span className={styles.priority} data-priority={event.priority}>
          {event.priority} priority · {eventStateLabels[event.status]}
        </span>
      </PageHeading>
      {event.status === "resolved" && (
        <div className={styles.resolved}>
          <strong>Resolved history.</strong> This event is immutable. Later
          concerns create separate linked records.
          {event.feedback && (
            <p>
              {event.feedback.actualEventLabel} ·{" "}
              {careTime(event.feedback.createdAt, snapshot.facility.timeZone)}
            </p>
          )}
        </div>
      )}
      <div className={`${styles.layout} ${styles.eventLayout}`}>
        <div className={styles.main}>
          <section
            className={styles.panel}
            aria-labelledby="event-evidence-heading"
          >
            <div className={styles.panelTitle}>
              <h2 id="event-evidence-heading">Observed evidence</h2>
              <span className={styles.meta}>{event.confidence.label}</span>
            </div>
            {event.confidence.limitation && (
              <p>{event.confidence.limitation}</p>
            )}
            {event.evidence.length ? (
              <ol className={styles.evidenceList}>
                {event.evidence.map((evidence, i) => (
                  <li key={evidence.evidenceId}>
                    <span className={styles.evidenceIndex}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3>{evidence.label}</h3>
                      <p>{evidence.observation}</p>
                      <time dateTime={evidence.recordedAt}>
                        {careTime(
                          evidence.recordedAt,
                          snapshot.facility.timeZone,
                        )}{" "}
                        · {evidence.quality} quality
                      </time>
                    </div>
                  </li>
                ))}
              </ol>
            ) : (
              <p>
                No observation evidence was supplied. The concern remains
                available for review.
              </p>
            )}
          </section>
          <section
            className={styles.panel}
            aria-labelledby="explanation-heading"
          >
            <h2 id="explanation-heading">Possible explanation</h2>
            <div className={styles.interpretation}>
              <strong>
                {event.interpretation.status === "complete"
                  ? "AI interpretation · possible explanation"
                  : event.interpretation.status === "pending"
                    ? "Analysis pending"
                    : "Analysis unavailable"}
              </strong>
              <p>
                {event.interpretation.summary ??
                  "No explanation is available. The concern remains visible for staff review."}
              </p>
              <p className={styles.meta}>{event.interpretation.uncertainty}</p>
            </div>
          </section>
          <section
            className={styles.panel}
            aria-labelledby="response-history-heading"
          >
            <h2 id="response-history-heading">Response history</h2>
            <ol className={styles.history} style={{ marginTop: 20 }}>
              {event.actionHistory.map((item, i) => (
                <li key={`${item.action}-${item.occurredAt}-${i}`}>
                  <h3>
                    {
                      {
                        opened: "Concern opened",
                        acknowledged: "Concern acknowledged",
                        checked: "Event moved to checked",
                        resolved: "Concern resolved",
                      }[item.action]
                    }
                  </h3>
                  <p>
                    {item.actorLabel} ·{" "}
                    {careTime(item.occurredAt, snapshot.facility.timeZone)}
                  </p>
                </li>
              ))}
              {checks.map((check) => (
                <li key={check.checkId}>
                  <h3>{outcomeLabels[check.outcome]}</h3>
                  <p>
                    {check.clientLabel} ·{" "}
                    {careTime(check.checkedAt, snapshot.facility.timeZone)}
                    {check.checkedAt !== check.recordedAt
                      ? ` · saved ${careTime(check.recordedAt, snapshot.facility.timeZone)}`
                      : ""}
                  </p>
                  {check.note && <p>{check.note}</p>}
                  {!check.completedCheck && (
                    <p>No completed resident check recorded by this outcome.</p>
                  )}
                </li>
              ))}
            </ol>
          </section>
          <section
            className={styles.panel}
            aria-labelledby="event-followup-heading"
          >
            <h2 id="event-followup-heading">
              Outstanding follow-up
              <span className={styles.count}>{followUps.length}</span>
            </h2>
            {followUps.length ? (
              <FollowUpList
                items={followUps}
                snapshot={snapshot}
                editable={event.status !== "resolved"}
              />
            ) : (
              <p className={styles.emptyCompact}>
                No outstanding follow-up returned.
              </p>
            )}
            <CompletedFollowUpHistory
              items={snapshot.followUps.filter(
                (item) => item.eventId === eventId,
              )}
              snapshot={snapshot}
            />
            {event.status !== "resolved" && (
              <FollowUpEditor
                key={eventId}
                event={event}
                timeZone={snapshot.facility.timeZone}
              />
            )}
          </section>
          {event.relatedEventIds.length > 0 && (
            <section className={styles.panel}>
              <h2>Related history</h2>
              <p>
                Related events retain their own records and response history.
              </p>
              <ul className={styles.plainList}>
                {event.relatedEventIds.map((id) => (
                  <li key={id}>
                    <Link className={styles.textLink} href={`/events/${id}`}>
                      Review related concern →
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
        <aside className={styles.rail}>
          {event.status !== "resolved" && (
            <EventActions key={eventId} event={event} snapshot={snapshot} />
          )}
          <section
            className={styles.panel}
            aria-labelledby="event-record-heading"
          >
            <h2 id="event-record-heading">Record & limitations</h2>
            <dl className={styles.facts}>
              <div>
                <dt>Resident</dt>
                <dd>
                  <Link
                    className={styles.textLink}
                    href={`/residents/${event.resident.residentId}`}
                  >
                    {residentName(
                      snapshot.profiles,
                      event.resident.residentId,
                      event.resident.displayLabel,
                    )}
                  </Link>
                </dd>
              </div>
              <div>
                <dt>Last evidence</dt>
                <dd>
                  {careTime(event.lastSignalAt, snapshot.facility.timeZone)}
                </dd>
              </div>
              <div>
                <dt>Evidence quality</dt>
                <dd>{event.confidence.dataQuality}</dd>
              </div>
              <div>
                <dt>Room monitoring</dt>
                <dd>{event.device.status}</dd>
              </div>
              {event.overdueAt && (
                <div>
                  <dt>Response due</dt>
                  <dd>
                    {careTime(event.overdueAt, snapshot.facility.timeZone)}
                  </dd>
                </div>
              )}
            </dl>
            <p>
              Follow {snapshot.facility.escalationContact}. A missing
              explanation or reading does not close this concern.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
