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

export type ResidentRecordsProps = Readonly<{
  records: readonly ResidentRecord[];
}>;

function FreshnessStatus({ record }: Readonly<{ record: ResidentRecord }>) {
  if (record.freshness.value === "stale") {
    return (
      <StatusIndicator
        axis="freshness"
        value="stale"
        lastCurrentUpdate={record.freshness.lastCurrentUpdate}
      />
    );
  }

  return <StatusIndicator axis="freshness" value={record.freshness.value} />;
}

function ResidentAction({ record }: Readonly<{ record: ResidentRecord }>) {
  return (
    <a
      className={styles.primaryAction}
      data-primary-action
      href={record.primaryAction.href}
      aria-label={`${record.primaryAction.label} for ${record.residentName}`}
    >
      {record.primaryAction.label}
    </a>
  );
}

function DeviceDetails({ record }: Readonly<{ record: ResidentRecord }>) {
  return (
    <details className={styles.deviceDetails}>
      <summary>Device details for {record.residentName}</summary>
      <div>
        <StatusIndicator axis="device" value={record.device} />
        <p>{record.deviceDetails}</p>
        <p>
          Last observed <time>{record.lastObserved}</time>
        </p>
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
  | Readonly<{ axis: "attention"; value: StatusValue<"attention">; detail?: string }>
  | Readonly<{ axis: "monitoring"; value: StatusValue<"monitoring">; detail?: string }>
  | Readonly<{ axis: "confidence"; value: StatusValue<"confidence">; detail?: string }>
  | Readonly<{ axis: "freshness"; value: StatusValue<"freshness">; detail?: string }>
  | Readonly<{ axis: "device"; value: StatusValue<"device">; detail?: string }>
  | Readonly<{ axis: "workflow"; value: StatusValue<"workflow">; detail?: string }>;

function CompactStatus(props: CompactStatusProps) {
  const label = getStatusLabel(props);
  const { axis, value, detail } = props;
  const axisLabel = getStatusAxisLabel(axis);
  const accessibleLabel = detail ? `${axisLabel}: ${label}; ${detail}` : `${axisLabel}: ${label}`;

  return (
    <span className={styles.compactStatus} data-axis={axis} data-value={value} aria-label={accessibleLabel}>
      <span>{axisLabel}</span>
      <strong>{label}</strong>
      {detail ? <small>{detail}</small> : null}
    </span>
  );
}

function InteractionCue({ interaction }: Readonly<{ interaction?: ResidentInteraction }>) {
  if (!interaction) return null;
  return <span className={styles.selectedCue}>{interaction === "hover" ? "Hover example" : "Selected record"}</span>;
}

function RecordEvidence({ record }: Readonly<{ record: ResidentRecord }>) {
  return (
    <div className={styles.evidence} data-evidence>
      <div>
        <StatusIndicator axis="confidence" value={record.confidence} />
      </div>
      <div>
        <FreshnessStatus record={record} />
      </div>
      <div>
        <StatusIndicator axis="monitoring" value={record.monitoring} />
      </div>
    </div>
  );
}

function MobileRecord({ record }: Readonly<{ record: ResidentRecord }>) {
  return (
    <article className={styles.recordCard} data-interaction={record.interaction} aria-label={`${record.residentName}, ${record.room}`}>
      <ResidentIdentity record={record} />
      <InteractionCue interaction={record.interaction} />
      <div className={styles.attentionReason} data-attention-reason>
        <span>Attention reason</span>
        <p>{record.attentionReason}</p>
      </div>
      <div className={styles.attentionPriority} data-attention-priority>
        <StatusIndicator axis="attention" value={record.attention} />
      </div>
      <RecordEvidence record={record} />
      <div className={styles.workflow} data-workflow>
        <StatusIndicator axis="workflow" value={record.workflow} />
      </div>
      <ResidentAction record={record} />
      <DeviceDetails record={record} />
    </article>
  );
}

function DesktopTable({ records }: ResidentRecordsProps) {
  return (
    <div className={styles.desktopTable}>
      <table>
        <caption>Synthetic resident monitoring records</caption>
        <thead>
          <tr>
            <th className={styles.residentColumn} scope="col">Resident</th>
            <th className={styles.attentionColumn} scope="col">Attention priority</th>
            <th className={styles.evidenceColumn} scope="col">Evidence</th>
            <th className={styles.operationsColumn} scope="col">Operations</th>
            <th className={styles.actionColumn} scope="col"><span className={styles.visuallyHidden}>Action</span></th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id} data-interaction={record.interaction}>
              <th className={styles.residentColumn} scope="row">
                <ResidentIdentity record={record} />
                <div className={styles.tableResidentReason}>
                  <span>Attention reason</span>
                  <p>{record.attentionReason}</p>
                </div>
                <InteractionCue interaction={record.interaction} />
              </th>
              <td className={styles.attentionColumn}><CompactStatus axis="attention" value={record.attention} /></td>
              <td className={styles.evidenceColumn}>
                <div className={styles.compactGroup}>
                  <CompactStatus axis="confidence" value={record.confidence} />
                  <CompactStatus axis="freshness" value={record.freshness.value} detail={record.freshness.value === "stale" && record.freshness.lastCurrentUpdate ? `last current update ${record.freshness.lastCurrentUpdate}` : undefined} />
                </div>
              </td>
              <td className={styles.operationsColumn}>
                <div className={styles.compactGroup}>
                  <CompactStatus
                    axis="monitoring"
                    value={record.monitoring}
                    detail={record.monitoring === "possible_multi_person" ? "Resident attribution unavailable; do not guess which resident caused this signal." : undefined}
                  />
                  <CompactStatus axis="device" value={record.device} />
                  <CompactStatus axis="workflow" value={record.workflow} />
                </div>
              </td>
              <td className={styles.actionColumn}><ResidentAction record={record} /></td>
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
