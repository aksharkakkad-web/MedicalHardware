"use client";

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
        <p className={styles.eyebrow}>Residents</p>
        <h1>Resident overview</h1>
        <p className={styles.intro}>
          Start with attention items, then check rooms with limited or unavailable monitoring.
        </p>
      </div>
      <p className={styles.updatedLabel}>Live mock workspace</p>
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

  return (
    <section className={styles.page}>
      <OverviewHeader />

      <div className={styles.summary} aria-label="Resident monitoring summary">
        <div><strong>{highPriorityCount}</strong><span>High-priority items</span></div>
        <div><strong>{activeCount}</strong><span>Active monitoring</span></div>
        <div><strong>{limitedCount}</strong><span>Limited, paused, or offline</span></div>
      </div>

      <div className={styles.sectionHeading}>
        <div>
          <h2>Rooms at a glance</h2>
          <p>Ordered by urgency so the most important room appears first.</p>
        </div>
        <span>{residents.length} monitored rooms</span>
      </div>

      <div className={styles.grid}>
        {residents.map((resident) => <ResidentCard key={resident.residentId} resident={resident} />)}
      </div>
    </section>
  );
}
