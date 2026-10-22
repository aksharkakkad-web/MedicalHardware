"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { FacilityTimeField } from "@/components/ui/facility-time-field";
import type {
  MonitoringEventDetail,
} from "@/lib/monitoring";
import {
  hasWorkspacePermission,
  useWorkspace,
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
  HistoricalPriority,
  ResolvedConcernStatus,
  FollowUpList,
  PermissionNotice,
  WorkspaceState,
} from "./care-shared";
import { messageFor } from "./care-response-actions";
import { useConcernResponseDialog } from "./care-response-dialog";
import styles from "./care-workspace.module.css";

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
  const { openResponse, responseDialog } = useConcernResponseDialog();
  const { snapshot, status } = useWorkspace();
  if (!snapshot || status === "error")
    return <WorkspaceState subject="Concern information" />;
  const event = snapshot.events.find((e) => e.eventId === eventId);
  if (!event) return <WorkspaceState subject="Concern information" />;
  const checks = snapshot.checks.filter((c) => c.eventId === eventId);
  const resolution = event.actionHistory.find((entry) => entry.action === "resolved");
  const resolvedAt = resolution?.occurredAt ?? event.feedback?.createdAt;
  const followUps = snapshot.followUps.filter(
    (f) => f.eventId === eventId && f.status !== "completed",
  );
  return (
    <div className={styles.page}>
      <Link className={styles.backLink} href="/events">
        ← Concerns
      </Link>
      <header className={styles.eventHeading}>
        <p className={styles.eventResident}>
          {event.resident.roomLabel} <span>·</span> {residentName(snapshot.profiles, event.resident.residentId, event.resident.displayLabel)}
        </p>
        <h1>{event.headline}</h1>
        <div className={styles.eventMetadata}>
          {event.status !== "resolved" && (
            <span className={styles.priority} data-priority={event.priority}>
              {event.priority} priority
            </span>
          )}
          {event.status !== "resolved" && <span className={styles.responseState} aria-label="Concern response state">{eventStateLabels[event.status]}</span>}
          <span className={styles.meta}>Opened {careTime(event.createdAt, snapshot.facility.timeZone)}</span>
        </div>
        {event.status !== "resolved" && <Button className={styles.detailResponseButton} onClick={() => openResponse(eventId)}>Response &amp; outcome</Button>}
      </header>
      {event.status === "resolved" && (
        <div className={styles.resolved}>
          <div className={styles.resolvedHeading}>
            <div className={styles.completionLine}>
              <ResolvedConcernStatus />
              {resolvedAt && <span>Completed {careTime(resolvedAt, snapshot.facility.timeZone)}</span>}
            </div>
            <HistoricalPriority priority={event.priority} />
          </div>
          <p>{event.feedback?.actualEventLabel ?? "No resolution note supplied"}</p>
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
              <span className={styles.evidenceStatus} data-quality={event.confidence.dataQuality}>
                {event.confidence.dataQuality === "unavailable" ? "Evidence unavailable" : `Evidence confidence: ${event.confidence.label}`}
              </span>
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
                        · {evidence.quality === "unavailable" ? "Evidence unavailable" : `${evidence.quality} quality`}
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
            <div className={styles.interpretation} data-analysis={event.interpretation.status}>
              <strong>
                {event.status === "resolved" ? "Historical interpretation" : event.interpretation.status === "complete"
                  ? "AI interpretation · possible explanation"
                  : event.interpretation.status === "pending"
                    ? "Analysis pending"
                    : "Analysis unavailable"}
              </strong>
              <p>
                {event.interpretation.summary ??
                  (event.status === "resolved" ? "No interpretation was available at review." : "No explanation is available. Staff review remains needed.")}
              </p>
              <p className={styles.meta}>
                {event.interpretation.uncertainty}
              </p>
              {event.status === "resolved" && <p className={styles.meta}>Preserved from the original review; this interpretation does not describe the resident’s current state.</p>}
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
            <section className={styles.actionPanel}><h2>Response &amp; outcome</h2><p>Acknowledge, record a check or explicitly resolve this concern.</p><Button onClick={() => openResponse(eventId)}>Open response</Button></section>
          )}
          <section
            className={styles.panel}
            aria-labelledby="event-record-heading"
          >
            <h2 id="event-record-heading">{event.status === "resolved" ? "Record at review" : "Record & limitations"}</h2>
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
                  <dt>{event.status === "resolved" ? "Original response due" : "Response due"}</dt>
                  <dd>
                    {careTime(event.overdueAt, snapshot.facility.timeZone)}
                  </dd>
                </div>
              )}
            </dl>
            <p>
              {event.status === "resolved"
                ? "This completed record preserves the evidence and response available at the time of review. Current monitoring is shown in the resident record."
                : <>Follow {snapshot.facility.escalationContact}. A missing explanation or reading does not close this concern.</>}
            </p>
          </section>
        </aside>
      </div>
      {responseDialog}
    </div>
  );
}
