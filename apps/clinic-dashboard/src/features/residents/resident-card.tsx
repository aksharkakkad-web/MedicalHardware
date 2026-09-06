import Link from "next/link";

import { ArrowIcon } from "@/components/icons/icons";
import type { ResidentOverviewItem } from "@/lib/monitoring";

import styles from "./resident-card.module.css";

const monitoringLabels: Record<ResidentOverviewItem["monitoring"]["state"], string> = {
  active: "Active",
  limited: "Limited",
  paused: "Paused",
  unavailable: "Unavailable",
};

const attentionLabels: Record<ResidentOverviewItem["attention"]["priority"], string> = {
  none: "No open items",
  watch: "Watch item",
  high: "Needs attention",
  critical: "Critical attention",
};

const deviceLabels: Record<ResidentOverviewItem["device"]["status"], string> = {
  online: "Online",
  degraded: "Degraded",
  offline: "Offline",
  unknown: "Unknown",
};

type ResidentStatusProps =
  | Readonly<{ axis: "attention"; value: ResidentOverviewItem["attention"]["priority"] }>
  | Readonly<{ axis: "monitoring"; value: ResidentOverviewItem["monitoring"]["state"] }>;

const axisLabels: Record<ResidentStatusProps["axis"], string> = {
  attention: "Attention",
  monitoring: "Monitoring",
};

function statusLabel(props: ResidentStatusProps): string {
  switch (props.axis) {
    case "attention": return attentionLabels[props.value];
    case "monitoring": return monitoringLabels[props.value];
  }
}

export function ResidentStatus(props: ResidentStatusProps) {
  const label = statusLabel(props);
  const isQuietDefault =
    (props.axis === "attention" && props.value === "none") ||
    (props.axis === "monitoring" && props.value === "active");

  return (
    <span
      className={styles.statusText}
      data-axis={props.axis}
      data-value={props.value}
      data-emphasis={isQuietDefault ? "quiet" : "semantic"}
      aria-label={`${axisLabels[props.axis]}: ${label}`}
    >
      <span className={styles.statusDot} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

function DeviceContext({ resident }: Readonly<{ resident: ResidentOverviewItem }>) {
  const label = deviceLabels[resident.device.status];

  return (
    <span
      className={styles.deviceContext}
      data-device-status={resident.device.status}
      aria-label={`Device: ${label}`}
    >
      <span className={styles.deviceDot} aria-hidden="true" />
      {label}
    </span>
  );
}

function formattedTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

export function ResidentCard({ resident }: Readonly<{ resident: ResidentOverviewItem }>) {
  const hasAttention = resident.attention.priority !== "none";
  const hasMonitoringException = resident.monitoring.state !== "active";
  const href = resident.attention.primaryEventId
    ? `/events/${resident.attention.primaryEventId}`
    : `/residents/${resident.residentId}`;
  const actionLabel = resident.attention.primaryEventId
    ? "Review event"
    : hasAttention
      ? "Review resident"
      : "Open resident";

  return (
    <article className={styles.card} data-priority={resident.attention.priority}>
      <Link className={styles.identity} href={`/residents/${resident.residentId}`}>
        <strong className={styles.name}>{resident.displayLabel}</strong>
        <span className={styles.room}>{resident.roomLabel}</span>
      </Link>

      <div className={styles.attention}>
        <span className={styles.factLabel}>Attention</span>
        <ResidentStatus axis="attention" value={resident.attention.priority} />
        {hasAttention && <small>{resident.attention.headline}</small>}
      </div>

      <div className={styles.monitoring}>
        <span className={styles.factLabel}>Monitoring</span>
        <ResidentStatus axis="monitoring" value={resident.monitoring.state} />
        {hasMonitoringException && <small>{resident.monitoring.contextLabel ?? resident.monitoring.reason}</small>}
      </div>

      <div className={styles.device} data-visible={resident.device.status !== "online" ? "true" : undefined}>
        <span className={styles.factLabel}>Device</span>
        <DeviceContext resident={resident} />
        {resident.device.status !== "online" && <small>{resident.device.label}</small>}
      </div>

      <time className={styles.updated} dateTime={resident.monitoring.lastUpdatedAt}>
        <span className={styles.updatedLabel}>Updated </span>
        {formattedTime(resident.monitoring.lastUpdatedAt)}
      </time>

      <Link className={styles.recordAction} href={href} aria-label={`${actionLabel} for ${resident.displayLabel}`}>
        <span className={styles.actionLabel}>{actionLabel}</span>
        <ArrowIcon />
      </Link>
    </article>
  );
}
