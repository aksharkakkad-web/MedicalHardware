import type { ReactNode } from "react";

import { Button } from "./button";
import buttonStyles from "./button.module.css";
import { StatusIndicator, type StatusValue } from "./status-indicator";
import styles from "./attention-item.module.css";

type AttentionRecordBase = Readonly<{
  id: string;
  residentName: string;
  room: string;
  attentionReason: string;
  attention: StatusValue<"attention">;
  freshness:
    | Readonly<{ value: "stale"; lastCurrentUpdate?: string }>
    | Readonly<{ value: Exclude<StatusValue<"freshness">, "stale"> }>;
  device: StatusValue<"device">;
  workflow: StatusValue<"workflow">;
  elapsed?: string;
  observedContext?: string;
  deviceDetails?: string;
  primaryAction:
    | Readonly<{ label: string; href: string }>
    | Readonly<{ label: string; onClick: () => void }>;
}>;

export type AttentionRecord = AttentionRecordBase &
  (
    | Readonly<{
        monitoring: "possible_multi_person";
        confidence: "unavailable";
      }>
    | Readonly<{
        monitoring: Exclude<StatusValue<"monitoring">, "possible_multi_person">;
        confidence: StatusValue<"confidence">;
      }>
  );

export type AttentionItemProps = Readonly<{ record: AttentionRecord; className?: string }>;

function FreshnessStatus({ record }: Readonly<{ record: AttentionRecord }>) {
  if (record.freshness.value === "stale") {
    return <StatusIndicator axis="freshness" value="stale" lastCurrentUpdate={record.freshness.lastCurrentUpdate} />;
  }

  return <StatusIndicator axis="freshness" value={record.freshness.value} />;
}

function StatusAxis({ axis, children }: Readonly<{ axis: string; children: ReactNode }>) {
  return <div className={styles.axis} data-testid={`attention-item-axis-${axis}`} data-axis={axis}>{children}</div>;
}

export function AttentionItem({ record, className }: AttentionItemProps) {
  const actionLabel = `${record.primaryAction.label} for ${record.residentName}`;
  const action = "href" in record.primaryAction ? (
    <a className={`${buttonStyles.button} ${buttonStyles.primary}`} href={record.primaryAction.href} aria-label={actionLabel} data-primary-action>
      {record.primaryAction.label}
    </a>
  ) : (
    <Button type="button" onClick={record.primaryAction.onClick} aria-label={actionLabel} data-primary-action>
      {record.primaryAction.label}
    </Button>
  );
  const multiPerson = record.monitoring === "possible_multi_person";
  const confidence = multiPerson ? "unavailable" : record.confidence;

  return (
    <article className={[styles.item, className].filter(Boolean).join(" ")} data-attention-item data-record-id={record.id} aria-label={`${record.residentName}, ${record.room}`}>
      <div className={styles.topline}>
        <div className={styles.identity}>
          <strong>{record.residentName}</strong>
          <span>{record.room}</span>
        </div>
        {record.elapsed ? <time className={styles.elapsed}>{record.elapsed}</time> : null}
      </div>

      <div className={styles.reason}>
        <span>Attention reason</span>
        <h3>{record.attentionReason}</h3>
      </div>

      <div className={styles.statuses} aria-label="Monitoring facts">
        <StatusAxis axis="attention"><StatusIndicator axis="attention" value={record.attention} /></StatusAxis>
        <StatusAxis axis="monitoring"><StatusIndicator axis="monitoring" value={record.monitoring} /></StatusAxis>
        {multiPerson ? <p className={styles.attributionLimit}>Resident-specific attribution is unavailable while multiple people may be present. Do not guess which person caused this signal.</p> : null}
        <StatusAxis axis="confidence"><StatusIndicator axis="confidence" value={confidence} /></StatusAxis>
        <StatusAxis axis="freshness"><FreshnessStatus record={record} /></StatusAxis>
        <StatusAxis axis="device"><StatusIndicator axis="device" value={record.device} /></StatusAxis>
        <StatusAxis axis="workflow"><StatusIndicator axis="workflow" value={record.workflow} /></StatusAxis>
      </div>

      {record.observedContext ? <p className={styles.context}><strong>Observed context</strong>{record.observedContext}</p> : null}

      <div className={styles.actionRow}>{action}</div>

      {record.deviceDetails ? (
        <details className={styles.deviceDetails}>
          <summary>Device details for {record.residentName}</summary>
          <p>{record.deviceDetails}</p>
        </details>
      ) : null}
    </article>
  );
}
