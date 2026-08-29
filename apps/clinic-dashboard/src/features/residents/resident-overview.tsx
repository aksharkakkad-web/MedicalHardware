"use client";

import Link from "next/link";
import { AlertIcon } from "@/components/icons/icons";
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
          Focus on the rooms that need a decision, then review every resident with monitoring context intact.
        </p>
      </div>
      <p className={styles.updatedLabel}><span aria-hidden="true" /> Live synthetic workspace</p>
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
  const attentionCount = residents.filter((resident) => resident.attention.priority !== "none").length;
  const onlineDeviceCount = residents.filter((resident) => resident.device.status === "online").length;
  const limitedDeviceCount = residents.filter((resident) => resident.device.status === "degraded").length;
  const unavailableDeviceCount = residents.filter((resident) => ["offline", "unknown"].includes(resident.device.status)).length;
  const primaryAttention = residents.find((resident) => resident.attention.priority !== "none" && resident.attention.primaryEventId);
  const activePercent = Math.round((activeCount / residents.length) * 100);
  const attentionLabel = `${attentionCount} ${attentionCount === 1 ? "resident needs" : "residents need"} attention`;

  return (
    <section className={styles.page}>
      <OverviewHeader />

      <div className={styles.overviewLayout}>
        <div className={styles.primaryColumn}>
          {primaryAttention ? (
            <section className={styles.attentionBanner} aria-labelledby="attention-heading">
              <span className={styles.alertMark}><AlertIcon /></span>
              <div className={styles.attentionCopy}>
                <h2 id="attention-heading">{attentionLabel}</h2>
                <p>{primaryAttention.attention.headline}</p>
                <small>{primaryAttention.displayLabel} · {primaryAttention.roomLabel} · Highest-priority open event</small>
              </div>
              <Link className={styles.reviewAction} href={`/events/${primaryAttention.attention.primaryEventId}`} aria-label="Review highest-priority event">Review event <span aria-hidden="true">→</span></Link>
            </section>
          ) : (
            <section className={styles.quietBanner} aria-labelledby="attention-heading">
              <div><h2 id="attention-heading">No open attention items</h2><p>Current resident records do not contain an open attention item.</p></div>
              <Link href="/events">View event history <span aria-hidden="true">→</span></Link>
            </section>
          )}

          <section className={styles.residentSection} aria-labelledby="resident-sheet-heading">
            <div className={styles.sectionHeading}>
              <div>
                <p className={styles.sectionEyebrow}>Resident inventory</p>
                <h2 id="resident-sheet-heading">Residents and rooms</h2>
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
        </div>

        <aside className={styles.contextRail} aria-label="Current clinic context">
          <section className={styles.contextCard}>
            <p className={styles.contextEyebrow}>Current coverage</p>
            <div className={styles.coverageSummary}>
              <div className={styles.coverageRing} style={{ "--coverage": `${activePercent * 3.6}deg` } as React.CSSProperties}><strong>{activePercent}%</strong></div>
              <div><strong>{activeCount} of {residents.length} active</strong><span>Resident-specific monitoring</span></div>
            </div>
            <ul className={styles.summaryList}>
              <SummaryRow label="Active" value={activeCount} tone="healthy" />
              <SummaryRow label="Limited or paused" value={limitedCount} tone="attention" />
              <SummaryRow label="Unavailable" value={unavailableCount} tone="unavailable" />
            </ul>
          </section>

          <section className={styles.contextCard}>
            <p className={styles.contextEyebrow}>Device health</p>
            <ul className={styles.summaryList}>
              <SummaryRow label="Online" value={onlineDeviceCount} tone="healthy" />
              <SummaryRow label="Limited" value={limitedDeviceCount} tone="attention" />
              <SummaryRow label="Unavailable" value={unavailableDeviceCount} tone="unavailable" />
            </ul>
            <p className={styles.contextNote}>Based on the device state attached to each resident record.</p>
          </section>

          <section className={styles.contextCallout}>
            <strong>{attentionCount} {attentionCount === 1 ? "resident flagged" : "residents flagged"} for attention</strong>
            <p>Includes watch, high, and critical attention states. Priority and monitoring availability remain separate.</p>
            <Link href="/events">Open event queue <span aria-hidden="true">→</span></Link>
          </section>
        </aside>
      </div>
    </section>
  );
}
