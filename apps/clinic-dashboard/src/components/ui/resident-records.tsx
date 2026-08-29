import { StatusIndicator, type StatusValue } from "./status-indicator";

import styles from "./resident-records.module.css";

export type ResidentRecord = Readonly<{
  id: string;
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
      <summary>Device details</summary>
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
    <article className={styles.recordCard}>
      <ResidentIdentity record={record} />
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
            <th scope="col">Resident</th>
            <th scope="col">Attention</th>
            <th scope="col">Monitoring</th>
            <th scope="col">Confidence</th>
            <th scope="col">Freshness</th>
            <th scope="col">Device</th>
            <th scope="col">Workflow</th>
            <th scope="col"><span className={styles.visuallyHidden}>Action</span></th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id}>
              <th scope="row">
                <ResidentIdentity record={record} />
              </th>
              <td><StatusIndicator axis="attention" value={record.attention} /></td>
              <td><StatusIndicator axis="monitoring" value={record.monitoring} /></td>
              <td><StatusIndicator axis="confidence" value={record.confidence} /></td>
              <td><FreshnessStatus record={record} /></td>
              <td><StatusIndicator axis="device" value={record.device} /></td>
              <td><StatusIndicator axis="workflow" value={record.workflow} /></td>
              <td><ResidentAction record={record} /></td>
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
