"use client";

import Link from "next/link";

import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import type {
  EventAction,
  MonitoringEventDetail,
} from "@/lib/monitoring";

import styles from "./event-detail.module.css";
import { EventHistory } from "./event-history";
import { EventResolutionForm } from "./event-resolution-form";
import { useEventDetail } from "./use-event-detail";

const statusPresentation: Record<
  MonitoringEventDetail["status"],
  { label: string; tone: StatusTone }
> = {
  detected: { label: "Detected", tone: "attention" },
  open: { label: "Open", tone: "critical" },
  acknowledged: { label: "Acknowledged", tone: "attention" },
  checked: { label: "Checked", tone: "attention" },
  resolved: { label: "Resolved", tone: "healthy" },
};

const priorityPresentation: Record<
  MonitoringEventDetail["priority"],
  { label: string; tone: StatusTone }
> = {
  watch: { label: "Watch priority", tone: "attention" },
  high: { label: "High priority", tone: "critical" },
  critical: { label: "Critical priority", tone: "critical" },
};

const nextAction: Partial<
  Record<MonitoringEventDetail["status"], { action: EventAction; label: string; explanation: string }>
> = {
  open: {
    action: "acknowledge",
    label: "Acknowledge event",
    explanation: "Tell the team that someone has seen this event.",
  },
  acknowledged: {
    action: "check",
    label: "Mark resident checked",
    explanation: "Record that a staff member checked on the resident.",
  },
};

const interpretationPresentation: Record<
  MonitoringEventDetail["interpretation"]["status"],
  { label: string; tone: StatusTone }
> = {
  pending: { label: "Explanation pending", tone: "attention" },
  complete: { label: "Explanation ready", tone: "neutral" },
  unavailable: { label: "Explanation unavailable", tone: "unavailable" },
};

const qualityTone: Record<
  MonitoringEventDetail["confidence"]["dataQuality"],
  StatusTone
> = {
  good: "healthy",
  limited: "attention",
  unavailable: "unavailable",
};

function formatTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

function LoadingEvent() {
  return (
    <section className={styles.page} aria-label="Loading event information" role="status">
      <div className={styles.loadingBlock} />
      <div className={styles.loadingGrid}>
        <div />
        <div />
      </div>
    </section>
  );
}

export function EventDetail({ eventId }: Readonly<{ eventId: string }>) {
  const result = useEventDetail(eventId);

  if (result.status === "loading") {
    return <LoadingEvent />;
  }

  if (result.status === "error") {
    return (
      <section className={styles.page}>
        <Link className={styles.backLink} href="/">← Back to residents</Link>
        <div className={styles.error} role="alert">
          <h1>Event information is unavailable</h1>
          <p>{result.message} This does not mean the resident is safe or the event is resolved.</p>
          <button type="button" onClick={result.retry}>Try again</button>
        </div>
      </section>
    );
  }

  const event = result.event;
  const status = statusPresentation[event.status];
  const priority = priorityPresentation[event.priority];
  const action = nextAction[event.status];
  const interpretation = interpretationPresentation[event.interpretation.status];

  return (
    <section className={styles.page}>
      <Link className={styles.backLink} href="/">← Back to residents</Link>

      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>{event.resident.roomLabel} · {event.resident.displayLabel}</p>
          <h1>{event.headline}</h1>
          <p className={styles.timestamp}>Detected {formatTime(event.createdAt)}</p>
        </div>
        <div className={styles.headerStatuses}>
          {event.overdue && <StatusPill label="Response overdue" tone="critical" />}
          <StatusPill label={priority.label} tone={priority.tone} />
          <StatusPill label={status.label} tone={status.tone} />
        </div>
      </header>

      <div className={styles.layout}>
        <div className={styles.primaryColumn}>
          <section className={styles.panel} aria-labelledby="evidence-heading">
            <div className={styles.panelHeading}>
              <div>
                <p className={styles.sectionLabel}>Objective evidence</p>
                <h2 id="evidence-heading">What the sensors observed</h2>
              </div>
              <StatusPill
                label={event.confidence.label}
                tone={qualityTone[event.confidence.dataQuality]}
              />
            </div>
            <p className={styles.safetyNote}>{event.confidence.limitation}</p>
            <ol className={styles.evidenceList}>
              {event.evidence.map((item) => (
                <li key={item.evidenceId}>
                  <div className={styles.evidenceMarker} aria-hidden="true" />
                  <div>
                    <div className={styles.evidenceTitle}>
                      <h3>{item.label}</h3>
                      <time dateTime={item.recordedAt}>{formatTime(item.recordedAt)}</time>
                    </div>
                    <p>{item.observation}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <section className={styles.panel} aria-labelledby="interpretation-heading">
            <div className={styles.panelHeading}>
              <div>
                <p className={styles.sectionLabel}>AI-assisted explanation</p>
                <h2 id="interpretation-heading">What this pattern may mean</h2>
              </div>
              <StatusPill
                label={interpretation.label}
                tone={interpretation.tone}
              />
            </div>
            {event.interpretation.summary ? (
              <p className={styles.interpretation}>{event.interpretation.summary}</p>
            ) : (
              <p className={styles.interpretation}>
                {event.interpretation.status === "pending"
                  ? "The AI explanation is still being prepared. The event remains visible and staff can act now."
                  : "No AI explanation is available. The event remains visible for staff review."}
              </p>
            )}
            <p className={styles.uncertainty}>{event.interpretation.uncertainty}</p>
          </section>

          <EventHistory event={event} />

          {(event.recurrenceCount > 1 || event.relatedEventIds.length > 0) && (
            <section className={styles.panel} aria-labelledby="related-heading">
              <p className={styles.sectionLabel}>Pattern history</p>
              <h2 id="related-heading">Related events</h2>
              <p className={styles.actionExplanation}>
                This pattern has appeared {event.recurrenceCount} times. Each event keeps its own permanent record.
              </p>
              <ul className={styles.relatedEvents}>
                {event.relatedEventIds.map((relatedEventId) => (
                  <li key={relatedEventId}>
                    <Link href={`/events/${relatedEventId}`}>View related event</Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className={styles.sideColumn}>
          <section className={styles.panel} aria-labelledby="action-heading">
            <p className={styles.sectionLabel}>Staff workflow</p>
            <h2 id="action-heading">Next action</h2>
            {action ? (
              <>
                <p className={styles.actionExplanation}>{action.explanation}</p>
                <button
                  className={styles.primaryButton}
                  type="button"
                  disabled={result.pendingAction !== null}
                  onClick={() => void result.performAction(action.action)}
                >
                  {result.pendingAction === action.action ? "Saving…" : action.label}
                </button>
              </>
            ) : event.status === "resolved" ? (
              <div className={styles.resolutionSummary}>
                <p className={styles.completed}>This event is resolved. Its history remains available.</p>
                {event.feedback && (
                  <dl>
                    <div><dt>Outcome</dt><dd>{event.resolutionOutcome?.replace("_", " ")}</dd></div>
                    <div><dt>What happened</dt><dd>{event.feedback.actualEventLabel}</dd></div>
                    <div><dt>Normal routine</dt><dd>{event.feedback.routine ? "Yes" : "No"}</dd></div>
                  </dl>
                )}
              </div>
            ) : event.status === "checked" ? (
              <EventResolutionForm
                isSaving={result.pendingAction === "resolve"}
                onSubmit={result.resolveWithFeedback}
              />
            ) : (
              <p className={styles.completed}>This event is still being prepared for staff review.</p>
            )}
            {result.actionError && <p className={styles.actionError} role="alert">{result.actionError}</p>}
          </section>

          <section className={styles.panel} aria-labelledby="quality-heading">
            <p className={styles.sectionLabel}>Monitoring quality</p>
            <h2 id="quality-heading">Data and device status</h2>
            <dl className={styles.facts}>
              <div><dt>Event type</dt><dd>{event.objectiveFamily}</dd></div>
              <div><dt>Confidence</dt><dd>{Math.round(event.confidence.value * 100)}%</dd></div>
              <div><dt>Data quality</dt><dd>{event.confidence.dataQuality}</dd></div>
              <div><dt>Device</dt><dd>{event.device.label}</dd></div>
              {event.overdueAt && <div><dt>Response due</dt><dd>{formatTime(event.overdueAt)}</dd></div>}
            </dl>
            <ul className={styles.sources} aria-label="Sensor source availability">
              {event.device.sources.map((source) => (
                <li key={source.label}>
                  <span>{source.label}</span>
                  <span data-status={source.status}>{source.status}</span>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </section>
  );
}
