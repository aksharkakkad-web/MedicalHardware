import Link from "next/link";

import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import type { ResidentOverviewItem } from "@/lib/monitoring";

import styles from "./resident-card.module.css";

const monitoringPresentation: Record<
  ResidentOverviewItem["monitoring"]["state"],
  { label: string; tone: StatusTone }
> = {
  active: { label: "Monitoring active", tone: "healthy" },
  limited: { label: "Monitoring limited", tone: "attention" },
  paused: { label: "Monitoring paused", tone: "neutral" },
  unavailable: { label: "Monitoring unavailable", tone: "unavailable" },
};

const attentionPresentation: Record<
  ResidentOverviewItem["attention"]["priority"],
  { label: string; tone: StatusTone }
> = {
  none: { label: "No open attention items", tone: "healthy" },
  watch: { label: "Watch item", tone: "attention" },
  high: { label: "Needs attention", tone: "critical" },
  critical: { label: "Critical attention", tone: "critical" },
};

const deviceHeadline: Record<
  Exclude<ResidentOverviewItem["device"]["status"], "online">,
  string
> = {
  degraded: "Device degraded",
  offline: "Device offline",
  unknown: "Device status unknown",
};

function formattedTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function ResidentCard({ resident }: Readonly<{ resident: ResidentOverviewItem }>) {
  const monitoring = monitoringPresentation[resident.monitoring.state];
  const attention = attentionPresentation[resident.attention.priority];
  const hasAttention = resident.attention.priority !== "none";

  return (
    <article className={styles.card} data-priority={resident.attention.priority}>
      <div className={styles.header}>
        <div>
          <p className={styles.room}>{resident.roomLabel}</p>
          <h2 className={styles.name}>{resident.displayLabel}</h2>
        </div>
        <StatusPill label={monitoring.label} tone={monitoring.tone} />
      </div>

      {resident.monitoring.contextLabel && (
        <p className={styles.contextLabel}>
          {resident.monitoring.contextLabel}
        </p>
      )}
      <p className={styles.reason}>{resident.monitoring.reason}</p>

      <div className={styles.details}>
        <div className={styles.attention}>
          <StatusPill label={attention.label} tone={attention.tone} />
          {hasAttention && (
            <p className={styles.attentionHeadline}>{resident.attention.headline}</p>
          )}
        </div>

        {resident.device.status !== "online" && (
          <div className={styles.deviceWarning}>
            <strong>{deviceHeadline[resident.device.status]}</strong>
            <span>{resident.device.label}</span>
          </div>
        )}
      </div>

      {resident.attention.primaryEventId && (
        <Link
          className={styles.reviewLink}
          href={`/events/${resident.attention.primaryEventId}`}
        >
          Review event <span aria-hidden="true">→</span>
        </Link>
      )}

      <p className={styles.updated}>
        Updated{" "}
        <time dateTime={resident.monitoring.lastUpdatedAt}>
          {formattedTime(resident.monitoring.lastUpdatedAt)}
        </time>
      </p>
    </article>
  );
}
