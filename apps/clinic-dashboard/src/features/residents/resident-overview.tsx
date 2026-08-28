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
        <h1>Clinic overview</h1>
        <p className={styles.intro}>
          See what needs attention, then move through each room with clear monitoring context.
        </p>
      </div>
      <p className={styles.updatedLabel}>Live synthetic workspace</p>
    </div>
  );
}

function LoadingOverview() {
  return (
    <div className={styles.skeletonGrid} role="status" aria-label="Loading resident information">
      {[0, 1, 2].map((item) => (
        <div className={styles.skeletonCard} key={item} aria-hidden="true">
          <span className={styles.skeletonShort} />
          <span className={styles.skeletonTitle} />
          <span className={styles.skeletonLine} />
          <span className={styles.skeletonLine} />
        </div>
      ))}
    </div>
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
  const limitedCount = residents.length - activeCount;
  const highPriorityCount = residents.filter((resident) => ["high", "critical"].includes(resident.attention.priority)).length;
  const primaryAttention = residents.find((resident) => ["high", "critical"].includes(resident.attention.priority) && resident.attention.primaryEventId);

  return (
    <section className={styles.page}>
      <OverviewHeader />

      {primaryAttention && <Link className={styles.attentionBanner} href={`/events/${primaryAttention.attention.primaryEventId}`}><span className={styles.alertMark}><AlertIcon /></span><span><strong>{primaryAttention.attention.headline}</strong><small>{primaryAttention.displayLabel} · {primaryAttention.roomLabel} · Staff review is required</small></span><span>Review now →</span></Link>}

      <div className={styles.summary} aria-label="Resident monitoring summary"><div><strong>{highPriorityCount}</strong><span>High priority</span></div><div><strong>{activeCount}</strong><span>Active monitoring</span></div><div><strong>{limitedCount}</strong><span>Limited, paused, or offline</span></div><Link href="/events">View all events →</Link></div>

      <div className={styles.sectionHeading}>
        <div>
          <h2>Residents and rooms</h2>
          <p>Ordered by urgency. Select a resident for their complete room record.</p>
        </div>
        <span>{residents.length} monitored rooms</span>
      </div>

      <div className={styles.grid}><div className={styles.columnLabels} aria-hidden="true"><span>Room and resident</span><span>Monitoring</span><span>Attention</span><span>Device</span><span>Updated</span><span /></div>
        {residents.map((resident) => <ResidentCard key={resident.residentId} resident={resident} />)}
      </div>
    </section>
  );
}
