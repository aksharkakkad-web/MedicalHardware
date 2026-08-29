"use client";

import Link from "next/link";
import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import type { ResidentOverviewItem } from "@/lib/monitoring";

import { ResidentCard } from "./resident-card";
import styles from "./resident-overview.module.css";
import { useResidentOverview } from "./use-resident-overview";

const priorityOrder: Record<ResidentOverviewItem["attention"]["priority"], number> = {
  critical: 4,
  high: 3,
  watch: 2,
  none: 1,
};

function OverviewHeader() {
  return (
    <div className={styles.headingRow}>
      <div>
        <p className={styles.eyebrow}>Care operations</p>
        <h1>Clinic overview</h1>
        <p className={styles.intro}>
          Start with residents who need review, then scan monitoring across every room.
        </p>
      </div>
    </div>
  );
}

function LoadingOverview() {
  return (
    <div className={styles.loadingLayout} role="status" aria-label="Loading resident information">
      <div className={styles.loadingMain} aria-hidden="true">
        <div className={styles.skeletonBanner}>
          <span className={styles.skeletonMark} />
          <span className={styles.skeletonCopy} />
        </div>
        <div className={styles.skeletonSheet}>
          {[0, 1, 2, 3].map((item) => (
            <div className={styles.skeletonRow} key={item}>
              <span className={styles.skeletonTitle} />
              <span className={styles.skeletonLine} />
              <span className={styles.skeletonLine} />
            </div>
          ))}
        </div>
      </div>
      <div className={styles.skeletonRail} aria-hidden="true">
        <span className={styles.skeletonTitle} />
        <span className={styles.skeletonLine} />
        <span className={styles.skeletonLine} />
      </div>
    </div>
  );
}

function SummaryRow({ label, value, tone = "neutral" }: Readonly<{ label: string; value: number; tone?: "healthy" | "attention" | "unavailable" | "neutral" }>) {
  return <li><span><i className={styles.summaryDot} data-tone={tone} aria-hidden="true" />{label}</span><strong>{value}</strong></li>;
}

const attentionLabels: Record<ResidentOverviewItem["attention"]["priority"], string> = {
  critical: "Critical attention",
  high: "Needs attention",
  watch: "Watch item",
  none: "No open attention items",
};

function AttentionQueue({ residents }: Readonly<{ residents: ResidentOverviewItem[] }>) {
  const attentionResidents = residents.filter((resident) => resident.attention.priority !== "none");

  if (attentionResidents.length === 0) {
    return (
      <section className={styles.quietQueue} aria-labelledby="attention-heading">
        <div>
          <p className={styles.sectionEyebrow}>Attention queue</p>
          <h2 id="attention-heading">No residents need attention</h2>
          <p>Current resident records do not contain an open attention item.</p>
        </div>
        <Link href="/events">View event history <span aria-hidden="true">→</span></Link>
      </section>
    );
  }

  return (
    <section className={styles.attentionQueue} aria-labelledby="attention-heading">
      <div className={styles.queueHeader}>
        <div>
          <p className={styles.sectionEyebrow}>Attention queue</p>
          <h2 id="attention-heading">Residents needing review</h2>
          <p>Open items are ordered by urgency.</p>
        </div>
        <span className={styles.queueCount}>{attentionResidents.length} open</span>
      </div>

      <ol className={styles.queueList}>
        {attentionResidents.map((resident) => {
          const eventHref = resident.attention.primaryEventId
            ? `/events/${resident.attention.primaryEventId}`
            : `/residents/${resident.residentId}`;
          const actionLabel = resident.attention.primaryEventId ? "Review event" : "Review resident";
          const tone: StatusTone = resident.attention.priority === "watch" ? "attention" : "critical";

          return (
            <li key={resident.residentId}>
              <Link className={styles.queueResident} href={`/residents/${resident.residentId}`}>
                <strong>{resident.displayLabel}</strong>
                <span>{resident.roomLabel}</span>
              </Link>
              <div className={styles.queueFinding}>
                <StatusPill label={attentionLabels[resident.attention.priority]} tone={tone} />
                <p>{resident.attention.headline}</p>
              </div>
              <Link className={styles.queueAction} href={eventHref}>
                {actionLabel} <span aria-hidden="true">→</span>
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function ResidentOverview() {
  const result = useResidentOverview();

  if (result.status === "loading") {
    return <section className={styles.page}><OverviewHeader /><LoadingOverview /></section>;
  }

  if (result.status === "error") {
    return (
      <section className={styles.page}>
        <OverviewHeader />
        <div className={styles.message} role="alert">
          <p className={styles.messageTitle}>Resident information is unavailable</p>
          <p>{result.message} This does not mean residents are safe or monitoring is active.</p>
          <button type="button" onClick={result.retry}>Retry</button>
        </div>
      </section>
    );
  }

  if (result.items.length === 0) {
    return (
      <section className={styles.page}>
        <OverviewHeader />
        <div className={styles.message} role="status">
          <p className={styles.messageTitle}>No resident information is available</p>
          <p>Check room assignments or try again later. No safety conclusion can be made.</p>
        </div>
      </section>
    );
  }

  const residents = [...result.items].sort((left, right) => {
    const priorityDifference = priorityOrder[right.attention.priority] - priorityOrder[left.attention.priority];
    return priorityDifference || left.roomLabel.localeCompare(right.roomLabel);
  });
  const activeCount = residents.filter((resident) => resident.monitoring.state === "active").length;
  const limitedCount = residents.filter((resident) => ["limited", "paused"].includes(resident.monitoring.state)).length;
  const unavailableCount = residents.filter((resident) => resident.monitoring.state === "unavailable").length;
  const onlineDeviceCount = residents.filter((resident) => resident.device.status === "online").length;
  const limitedDeviceCount = residents.filter((resident) => resident.device.status === "degraded").length;
  const unavailableDeviceCount = residents.filter((resident) => ["offline", "unknown"].includes(resident.device.status)).length;

  return (
    <section className={styles.page}>
      <OverviewHeader />

      <div className={styles.overviewLayout}>
        <div className={styles.primaryColumn}>
          <AttentionQueue residents={residents} />
        </div>

        <aside className={styles.contextRail} aria-label="Current clinic context">
          <section className={styles.contextCard}>
            <div className={styles.contextBlock}>
              <p className={styles.contextEyebrow}>Monitoring coverage</p>
              <div className={styles.coverageSummary}>
                <strong>{activeCount} of {residents.length}</strong>
                <span>rooms actively monitoring</span>
              </div>
              <ul className={styles.summaryList}>
                <SummaryRow label="Active" value={activeCount} tone="healthy" />
                <SummaryRow label="Limited or paused" value={limitedCount} tone="attention" />
                <SummaryRow label="Unavailable" value={unavailableCount} tone="unavailable" />
              </ul>
            </div>

            <div className={styles.contextDivider} />

            <div className={styles.contextBlock}>
              <p className={styles.contextEyebrow}>Device health</p>
              <ul className={styles.summaryList}>
                <SummaryRow label="Online" value={onlineDeviceCount} tone="healthy" />
                <SummaryRow label="Limited" value={limitedDeviceCount} tone="attention" />
                <SummaryRow label="Unavailable" value={unavailableDeviceCount} tone="unavailable" />
              </ul>
            </div>
          </section>
        </aside>
      </div>

      <section className={styles.residentSection} aria-labelledby="resident-sheet-heading">
        <div className={styles.sectionHeading}>
          <div>
            <p className={styles.sectionEyebrow}>Resident inventory</p>
            <h2 id="resident-sheet-heading">All residents</h2>
            <p>Ordered by urgency. Open a resident for the complete room record.</p>
          </div>
          <span>{residents.length} monitored rooms</span>
        </div>

        <div className={styles.grid}>
          <div className={styles.columnLabels} aria-hidden="true"><span>Resident and room</span><span>Monitoring</span><span>Attention</span><span>Device</span><span>Updated</span><span /></div>
          {residents.map((resident) => <ResidentCard key={resident.residentId} resident={resident} />)}
          <Link className={styles.sheetFooter} href="/events">View all events <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </section>
  );
}
