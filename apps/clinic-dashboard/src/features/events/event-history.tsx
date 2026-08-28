import type { EventHistoryAction, MonitoringEventDetail } from "@/lib/monitoring";

import styles from "./event-detail.module.css";

const actionLabels: Record<EventHistoryAction, string> = {
  opened: "Event opened",
  acknowledged: "Event acknowledged",
  checked: "Resident checked",
  resolved: "Event resolved",
};

function formatTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

export function EventHistory({
  event,
}: Readonly<{ event: MonitoringEventDetail }>) {
  return (
    <section className={styles.panel} aria-labelledby="history-heading">
      <p className={styles.sectionLabel}>Audit trail</p>
      <h2 id="history-heading">Event history</h2>
      <ol className={styles.historyList}>
        {event.actionHistory.map((item, index) => (
          <li key={`${item.action}-${item.occurredAt}-${index}`}>
            <span className={styles.historyMarker} aria-hidden="true" />
            <div>
              <strong>{actionLabels[item.action]}</strong>
              <p>{item.actorLabel} · <time dateTime={item.occurredAt}>{formatTime(item.occurredAt)}</time></p>
              {item.resolutionOutcome && <small>Outcome: {item.resolutionOutcome.replace("_", " ")}</small>}
            </div>
          </li>
        ))}
        {event.feedback && (
          <li>
            <span className={styles.historyMarker} aria-hidden="true" />
            <div>
              <strong>Feedback saved</strong>
              <p>{event.feedback.submittedBy} · <time dateTime={event.feedback.createdAt}>{formatTime(event.feedback.createdAt)}</time></p>
              <small>{event.feedback.actualEventLabel}</small>
            </div>
          </li>
        )}
      </ol>
    </section>
  );
}
