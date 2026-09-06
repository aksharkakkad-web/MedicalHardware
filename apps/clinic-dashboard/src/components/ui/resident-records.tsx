import { ArrowIcon } from "../icons/icons";
import { getStatusAxisLabel, getStatusLabel, StatusIndicator, type StatusValue } from "./status-indicator";

import styles from "./resident-records.module.css";

export type ResidentInteraction = "hover" | "selected";

export type ResidentRecord = Readonly<{
  id: string;
  interaction?: ResidentInteraction;
  residentName: string;
  room: string;
  attentionReason: string;
  attention: StatusValue<"attention">;
  monitoring: StatusValue<"monitoring">;
  confidence: StatusValue<"confidence">;
  freshness:
    | Readonly<{ value: "stale"; lastCurrentUpdate?: string }>
    | Readonly<{ value: Exclude<StatusValue<"freshness">, "stale"> }>;
  device: StatusValue<"device">;
  workflow: StatusValue<"workflow">;
  primaryAction: Readonly<{ label: string; href: string }>;
  deviceDetails: string;
  lastObserved: string;
}>;

export type ResidentRecordsProps = Readonly<{ records: readonly ResidentRecord[] }>;

const shortLabels = {
  attention: { critical: "Critical", high: "High", watch: "Watch", none: "No priority" },
  monitoring: {
    active: "Monitoring active",
    away: "Resident away",
    possible_multi_person: "Multi-person possible",
    paused: "Monitoring paused",
    calibrating: "Calibrating",
    unavailable: "Unavailable",
  },
  confidence: { high: "High confidence", medium: "Medium confidence", low: "Low confidence", unavailable: "Confidence unavailable" },
  freshness: { current: "Current", delayed: "Delayed", stale: "Stale", unknown: "Update unknown" },
} as const;

function ResidentAction({ record, compact = false }: Readonly<{ record: ResidentRecord; compact?: boolean }>) {
  return (
    <a
      className={compact ? styles.rowAction : styles.primaryAction}
      data-primary-action
      href={record.primaryAction.href}
      aria-label={`${record.primaryAction.label} for ${record.residentName}`}
    >
      {compact ? <ArrowIcon /> : record.primaryAction.label}
    </a>
  );
}

function DeviceDetails({ record }: Readonly<{ record: ResidentRecord }>) {
  return (
    <details className={styles.deviceDetails}>
      <summary>More details for {record.residentName}</summary>
      <div>
        <StatusIndicator axis="device" value={record.device} />
        <StatusIndicator axis="workflow" value={record.workflow} />
        <p>{record.deviceDetails}</p>
      </div>
    </details>
  );
}

function ResidentIdentity({ record }: Readonly<{ record: ResidentRecord }>) {
  return (
    <div className={styles.recordIdentity} data-record-identity>
      <strong>{record.residentName}</strong>
      <span>{record.room}</span>
    </div>
  );
}

type CompactStatusProps =
  | Readonly<{ axis: "attention"; value: StatusValue<"attention"> }>
  | Readonly<{ axis: "monitoring"; value: StatusValue<"monitoring"> }>
  | Readonly<{ axis: "confidence"; value: StatusValue<"confidence"> }>
  | Readonly<{ axis: "freshness"; value: StatusValue<"freshness"> }>;

function CompactStatus(props: CompactStatusProps) {
  const canonicalLabel = getStatusLabel(props);
  const axisLabel = getStatusAxisLabel(props.axis);
  const axisLabels = shortLabels[props.axis] as Record<string, string>;
  const isQuietDefault =
    (props.axis === "attention" && props.value === "none") ||
    (props.axis === "monitoring" && props.value === "active") ||
    (props.axis === "confidence" && props.value === "high") ||
    (props.axis === "freshness" && props.value === "current");

  return (
    <span className={styles.compactStatus} data-axis={props.axis} data-value={props.value} data-emphasis={isQuietDefault ? "quiet" : "semantic"} aria-label={`${axisLabel}: ${canonicalLabel}`}>
      <span className={styles.statusDot} aria-hidden="true" />
      <span>{axisLabels[props.value]}</span>
    </span>
  );
}

function MobileRecord({ record }: Readonly<{ record: ResidentRecord }>) {
  return (
    <article className={styles.recordCard} data-interaction={record.interaction} aria-label={`${record.residentName}, ${record.room}`}>
      <ResidentIdentity record={record} />
      <div className={styles.attentionReason} data-attention-reason data-attention-priority>
        <CompactStatus axis="attention" value={record.attention} />
        <p>{record.attentionReason}</p>
      </div>
      <div className={styles.mobileEvidence} data-evidence>
        <div>
          <CompactStatus axis="monitoring" value={record.monitoring} />
          {record.confidence !== "high" ? <CompactStatus axis="confidence" value={record.confidence} /> : null}
        </div>
        <div>
          <time>{record.lastObserved}</time>
          {record.freshness.value !== "current" ? <CompactStatus axis="freshness" value={record.freshness.value} /> : null}
        </div>
      </div>
      <ResidentAction record={record} compact />
      <DeviceDetails record={record} />
    </article>
  );
}

function DesktopTable({ records }: ResidentRecordsProps) {
  return (
    <div className={styles.desktopTable}>
      <div className={styles.tableToolbar}>
        <div><strong>Resident records</strong><span>{records.length} monitored rooms</span></div>
        <div className={styles.toolbarActions} aria-label="Resident table tools">
          <button type="button">Search</button>
          <button type="button">Filter</button>
        </div>
      </div>
      <table>
        <caption className={styles.visuallyHidden}>Synthetic resident monitoring records</caption>
        <thead>
          <tr>
            <th className={styles.residentColumn} scope="col">Resident</th>
            <th className={styles.attentionColumn} scope="col">Attention</th>
            <th className={styles.monitoringColumn} scope="col">Monitoring</th>
            <th className={styles.updatedColumn} scope="col">Updated</th>
            <th className={styles.actionColumn} scope="col"><span className={styles.visuallyHidden}>Open record</span></th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id} data-interaction={record.interaction} aria-selected={record.interaction === "selected" || undefined}>
              <th className={styles.residentColumn} scope="row"><ResidentIdentity record={record} /></th>
              <td className={styles.attentionColumn}>
                <CompactStatus axis="attention" value={record.attention} />
                <span className={styles.secondaryLine}>{record.attentionReason}</span>
              </td>
              <td className={styles.monitoringColumn}>
                <CompactStatus axis="monitoring" value={record.monitoring} />
                {record.confidence !== "high" ? <CompactStatus axis="confidence" value={record.confidence} /> : null}
              </td>
              <td className={styles.updatedColumn}>
                <time>{record.lastObserved}</time>
                {record.freshness.value !== "current" ? <CompactStatus axis="freshness" value={record.freshness.value} /> : null}
              </td>
              <td className={styles.actionColumn}><ResidentAction record={record} compact /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ResidentRecords({ records }: ResidentRecordsProps) {
  return (
    <div className={styles.records}>
      <DesktopTable records={records} />
      <div className={styles.mobileRecords} data-testid="resident-records-mobile">
        {records.map((record) => <MobileRecord key={record.id} record={record} />)}
      </div>
    </div>
  );
}
