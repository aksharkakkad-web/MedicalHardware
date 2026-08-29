import Link from "next/link";

import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import { ArrowIcon } from "@/components/icons/icons";
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
      <Link className={styles.identity} href={`/residents/${resident.residentId}`}><strong className={styles.name}>{resident.displayLabel}</strong><span className={styles.room}>{resident.roomLabel}</span></Link>
      <div className={styles.monitoring}><StatusPill label={monitoring.label} tone={monitoring.tone} /><small>{resident.monitoring.contextLabel ?? resident.monitoring.reason}</small></div>
      <div className={styles.attention}><StatusPill label={attention.label} tone={attention.tone} />{hasAttention && <small>{resident.attention.headline}</small>}</div>
      <div className={styles.device}><strong>{resident.device.status === "online" ? "Device online" : deviceHeadline[resident.device.status]}</strong><small>{resident.device.label}</small></div>
      <time className={styles.updated} dateTime={resident.monitoring.lastUpdatedAt}>{formattedTime(resident.monitoring.lastUpdatedAt)}</time>
      <div className={styles.actions}>{resident.attention.primaryEventId && <Link className={styles.reviewLink} href={`/events/${resident.attention.primaryEventId}`}>Review event</Link>}<Link className={styles.detailLink} href={`/residents/${resident.residentId}`} aria-label={`View ${resident.displayLabel}`}><ArrowIcon /></Link></div>
    </article>
  );
}
