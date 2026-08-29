import { useId } from "react";

import styles from "./status-indicator.module.css";

export const statusValues = {
  attention: ["critical", "high", "watch", "none"],
  monitoring: ["active", "away", "possible_multi_person", "paused", "calibrating", "unavailable"],
  confidence: ["high", "medium", "low", "unavailable"],
  freshness: ["current", "delayed", "stale", "unknown"],
  device: ["healthy", "degraded", "offline", "maintenance"],
  workflow: ["new", "acknowledged", "investigating", "resolved"],
} as const;

export type StatusAxis = keyof typeof statusValues;
export type StatusValue<Axis extends StatusAxis> = (typeof statusValues)[Axis][number];

type SharedStatusIndicatorProps = Readonly<{ className?: string }>;

export type StatusIndicatorProps = {
  [Axis in StatusAxis]: Readonly<{
    axis: Axis;
    value: StatusValue<Axis>;
  }> &
    (Axis extends "freshness" ? Readonly<{ lastCurrentUpdate?: string }> : Readonly<unknown>) &
    SharedStatusIndicatorProps;
}[StatusAxis];

const axisLabels: Record<StatusAxis, string> = {
  attention: "Attention",
  monitoring: "Monitoring",
  confidence: "Confidence",
  freshness: "Freshness",
  device: "Device",
  workflow: "Workflow",
};

const valueLabels: { [Axis in StatusAxis]: Record<StatusValue<Axis>, string> } = {
  attention: {
    critical: "Critical attention priority",
    high: "High attention priority",
    watch: "Watch attention priority",
    none: "No attention priority",
  },
  monitoring: {
    active: "Monitoring current",
    away: "Monitoring away",
    possible_multi_person: "Monitoring possible multi-person",
    paused: "Monitoring paused",
    calibrating: "Monitoring calibrating",
    unavailable: "Monitoring unavailable",
  },
  confidence: {
    high: "High confidence",
    medium: "Medium confidence",
    low: "Low confidence",
    unavailable: "Confidence unavailable",
  },
  freshness: {
    current: "Freshness current",
    delayed: "Freshness delayed",
    stale: "Stale",
    unknown: "Freshness unknown",
  },
  device: {
    healthy: "Healthy device",
    degraded: "Degraded device",
    offline: "Offline device",
    maintenance: "Device maintenance",
  },
  workflow: {
    new: "Workflow new",
    acknowledged: "Workflow acknowledged",
    investigating: "Workflow investigating",
    resolved: "Workflow resolved",
  },
};

const descriptions: { [Axis in StatusAxis]: Record<StatusValue<Axis>, string> } = {
  attention: {
    critical: "Highest priority for caregiver review; review the evidence before acting.",
    high: "High priority for caregiver review; review the evidence before acting.",
    watch: "Review when practical; this is an attention priority, not a diagnosis.",
    none: "No attention priority is indicated by this synthetic example.",
  },
  monitoring: {
    active: "Resident attribution is usable for this synthetic example.",
    away: "Resident is away; resident-specific baseline learning is paused.",
    possible_multi_person:
      "Resident-specific attribution is unavailable; do not guess which person caused a signal.",
    paused: "Resident-specific output is unavailable until monitoring resumes.",
    calibrating: "Resident-specific output may be unavailable while setup settles.",
    unavailable: "No current resident-specific evidence can be shown.",
  },
  confidence: {
    high: "Evidence quality supports a high-confidence output.",
    medium: "Evidence quality is mixed; review the surrounding context.",
    low: "Evidence quality is limited; treat resident-specific output cautiously.",
    unavailable: "Evidence quality is unavailable; do not draw a resident-specific conclusion.",
  },
  freshness: {
    current: "Evidence is current.",
    delayed: "The latest evidence is delayed; review before treating it as current.",
    stale: "Current evidence may have changed since the last current update.",
    unknown: "The last current update is unknown; do not treat values as live.",
  },
  device: {
    healthy: "Room sources are reporting.",
    degraded: "One or more room sources may be limited.",
    offline: "Room unit is not currently reporting.",
    maintenance: "Room monitoring may be unavailable during device work.",
  },
  workflow: {
    new: "New work item; review event.",
    acknowledged: "Acknowledged; follow up with the available evidence.",
    investigating: "Keep the event open while checking.",
    resolved: "Resolved; this history remains immutable.",
  },
};

function getDescription(props: StatusIndicatorProps): string {
  if (props.axis === "freshness" && props.value === "stale") {
    return props.lastCurrentUpdate
      ? `Last current update: ${props.lastCurrentUpdate}. ${descriptions.freshness.stale}`
      : `Last current update is not available. ${descriptions.freshness.stale}`;
  }

  switch (props.axis) {
    case "attention":
      return descriptions.attention[props.value];
    case "monitoring":
      return descriptions.monitoring[props.value];
    case "confidence":
      return descriptions.confidence[props.value];
    case "freshness":
      return descriptions.freshness[props.value];
    case "device":
      return descriptions.device[props.value];
    case "workflow":
      return descriptions.workflow[props.value];
  }
}

function getLabel(props: StatusIndicatorProps): string {
  switch (props.axis) {
    case "attention":
      return valueLabels.attention[props.value];
    case "monitoring":
      return valueLabels.monitoring[props.value];
    case "confidence":
      return valueLabels.confidence[props.value];
    case "freshness":
      return valueLabels.freshness[props.value];
    case "device":
      return valueLabels.device[props.value];
    case "workflow":
      return valueLabels.workflow[props.value];
  }
}

export function StatusIndicator(props: StatusIndicatorProps) {
  const { axis, value, className } = props;
  const id = useId();
  const labelId = `${id}-label`;
  const descriptionId = `${id}-description`;
  const label = getLabel(props);
  const description = getDescription(props);

  return (
    <span
      className={[styles.indicator, className].filter(Boolean).join(" ")}
      data-axis={axis}
      data-value={value}
      role="status"
      aria-labelledby={labelId}
      aria-describedby={descriptionId}
    >
      <span className={styles.marker} aria-hidden="true" />
      <span className={styles.content}>
        <span className={styles.axis}>{axisLabels[axis]}</span>
        <span className={styles.label} id={labelId}>
          {label}
        </span>
        <span className={styles.description} id={descriptionId}>
          {description}
        </span>
      </span>
    </span>
  );
}
