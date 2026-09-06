"use client";

import Link from "next/link";

import { ArrowIcon } from "@/components/icons/icons";
import { Button } from "@/components/ui/button";
import type { ResidentOverviewItem } from "@/lib/monitoring";

import { ResidentCard, ResidentStatus } from "./resident-card";
import styles from "./resident-overview.module.css";
import { useResidentOverview } from "./use-resident-overview";

const priorityOrder: Record<ResidentOverviewItem["attention"]["priority"], number> = {
  critical: 4,
  high: 3,
  watch: 2,
  none: 1,
};

function OverviewHeader({
  attentionCount,
  residentCount,
}: Readonly<{ attentionCount?: number; residentCount?: number }>) {
  return (
    <header className={styles.pageHeader}>
      <div className={styles.headingRow}>
        <div>
          <h1>Clinic overview</h1>
          <p className={styles.intro}>
            {residentCount === undefined || attentionCount === undefined
              ? "Review current resident signals and monitoring coverage."
              : `${residentCount} resident records · ${attentionCount} ${attentionCount === 1 ? "needs" : "need"} review`}
          </p>
        </div>
        <Link className={styles.eventQueueLink} href="/events" aria-label="View event queue">
          View event queue <ArrowIcon />
        </Link>
      </div>
    </header>
  );
}

type SummaryTone =
  | "critical"
  | "high"
  | "watch"
  | "active"
  | "limited"
  | "paused"
  | "unavailable"
  | "online"
  | "degraded"
  | "offline"
  | "unknown";

type SummaryItem = Readonly<{
  label: string;
  value: number;
  tone: SummaryTone;
}>;

function SummaryLegend({ items }: Readonly<{ items: readonly SummaryItem[] }>) {
  return (
    <ul className={styles.summaryLegend}>
      {items.map((item) => (
        <li key={item.label}>
          <span><i className={styles.summaryDot} data-tone={item.tone} aria-hidden="true" />{item.label}</span>
          <strong>{item.value}</strong>
        </li>
      ))}
    </ul>
  );
}

function DistributionBar({
  label,
  items,
}: Readonly<{ label: string; items: readonly SummaryItem[] }>) {
  return (
    <div className={styles.distributionBar} role="img" aria-label={label}>
      {items.filter((item) => item.value > 0).map((item) => (
        <span
          key={item.label}
          data-tone={item.tone}
          style={{ flexGrow: item.value }}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

function OperationalSummary({ residents }: Readonly<{ residents: ResidentOverviewItem[] }>) {
  const total = residents.length;
  const monitoringCounts = {
    active: residents.filter((resident) => resident.monitoring.state === "active").length,
    limited: residents.filter((resident) => resident.monitoring.state === "limited").length,
    paused: residents.filter((resident) => resident.monitoring.state === "paused").length,
    unavailable: residents.filter((resident) => resident.monitoring.state === "unavailable").length,
  };
  const deviceCounts = {
    online: residents.filter((resident) => resident.device.status === "online").length,
    offline: residents.filter((resident) => resident.device.status === "offline").length,
    unknown: residents.filter((resident) => resident.device.status === "unknown").length,
    degraded: residents.filter((resident) => resident.device.status === "degraded").length,
  };
  const attentionCount = residents.filter((resident) => resident.attention.priority !== "none").length;
  const attentionCounts = {
    critical: residents.filter((resident) => resident.attention.priority === "critical").length,
    high: residents.filter((resident) => resident.attention.priority === "high").length,
    watch: residents.filter((resident) => resident.attention.priority === "watch").length,
  };
  const attentionItems: readonly SummaryItem[] = [
    { label: "Critical", value: attentionCounts.critical, tone: "critical" },
    { label: "High", value: attentionCounts.high, tone: "high" },
    { label: "Watch", value: attentionCounts.watch, tone: "watch" },
  ];
  const monitoringItems: readonly SummaryItem[] = [
    { label: "Active", value: monitoringCounts.active, tone: "active" },
    { label: "Limited", value: monitoringCounts.limited, tone: "limited" },
    { label: "Paused", value: monitoringCounts.paused, tone: "paused" },
    { label: "Unavailable", value: monitoringCounts.unavailable, tone: "unavailable" },
  ];
  const deviceItems: readonly SummaryItem[] = [
    { label: "Online", value: deviceCounts.online, tone: "online" },
    { label: "Degraded", value: deviceCounts.degraded, tone: "degraded" },
    { label: "Offline", value: deviceCounts.offline, tone: "offline" },
    { label: "Unknown", value: deviceCounts.unknown, tone: "unknown" },
  ];

  return (
    <aside className={styles.operationalSummary} aria-label="Current clinic context">
      <section
        className={styles.summarySection}
        aria-label={`Needs review: ${attentionCount} of ${total} residents`}
      >
        <p className={styles.summaryLabel}>Needs review</p>
        <p className={styles.coverageValue}>
          <strong>{attentionCount}</strong>
          <span>of {total} residents</span>
        </p>
        <DistributionBar
          label={`Review distribution: ${attentionCounts.critical} critical, ${attentionCounts.high} high, ${attentionCounts.watch} watch`}
          items={attentionItems}
        />
        <SummaryLegend items={attentionItems} />
      </section>

      <section
        className={styles.summarySection}
        aria-label={`Monitoring coverage: ${monitoringCounts.active} of ${total} active`}
      >
        <p className={styles.summaryLabel}>Monitoring coverage</p>
        <p className={styles.coverageValue}>
          <strong>{monitoringCounts.active} of {total}</strong>
          <span>active</span>
        </p>
        <DistributionBar
          label={`Monitoring distribution: ${monitoringCounts.active} active, ${monitoringCounts.limited} limited, ${monitoringCounts.paused} paused, ${monitoringCounts.unavailable} unavailable`}
          items={monitoringItems}
        />
        <SummaryLegend items={monitoringItems} />
      </section>

      <section
        className={styles.summarySection}
        aria-label={`Device health: ${deviceCounts.online} of ${total} online`}
      >
        <p className={styles.summaryLabel}>Device health</p>
        <p className={styles.coverageValue}>
          <strong>{deviceCounts.online} of {total}</strong>
          <span>online</span>
        </p>
        <DistributionBar
          label={`Device distribution: ${deviceCounts.online} online, ${deviceCounts.degraded} degraded, ${deviceCounts.offline} offline, ${deviceCounts.unknown} unknown`}
          items={deviceItems}
        />
        <SummaryLegend items={deviceItems} />
      </section>
    </aside>
  );
}

function LoadingOverview() {
  return (
    <div className={styles.loadingLayout} role="status" aria-label="Loading resident information">
      <div className={styles.skeletonBanner} aria-hidden="true">
        <span className={styles.skeletonMark} />
        <span className={styles.skeletonCopy} />
      </div>
      <div className={styles.skeletonSummary} aria-hidden="true">
        <span className={styles.skeletonTitle} />
        <span className={styles.skeletonLine} />
      </div>
      <div className={styles.skeletonSheet} aria-hidden="true">
        {[0, 1, 2, 3].map((item) => (
          <div className={styles.skeletonRow} key={item}>
            <span className={styles.skeletonTitle} />
            <span className={styles.skeletonLine} />
          </div>
        ))}
      </div>
    </div>
  );
}

function eventHref(resident: ResidentOverviewItem): string {
  return resident.attention.primaryEventId
    ? `/events/${resident.attention.primaryEventId}`
    : `/residents/${resident.residentId}`;
}

function actionLabel(resident: ResidentOverviewItem): string {
  return resident.attention.primaryEventId ? "Review event" : "Review resident";
}

function formattedTime(timestamp: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(timestamp));
}

function LeadSignal({ resident }: Readonly<{ resident: ResidentOverviewItem }>) {
  return (
    <article className={styles.leadSignal} data-priority={resident.attention.priority}>
      <div className={styles.leadMeta}>
        <ResidentStatus axis="attention" value={resident.attention.priority} />
        <span>{resident.roomLabel}</span>
      </div>

      <Link className={styles.leadResident} href={`/residents/${resident.residentId}`}>
        <strong>{resident.displayLabel}</strong>
      </Link>
      <p className={styles.leadFinding}>{resident.attention.headline}</p>

      <div className={styles.leadFooter}>
        <p>
          <time dateTime={resident.monitoring.lastUpdatedAt}>Updated {formattedTime(resident.monitoring.lastUpdatedAt)}</time>
          <span aria-hidden="true"> · </span>
          <span>{resident.monitoring.contextLabel ?? resident.monitoring.reason}</span>
        </p>
        <Link
          className={styles.leadAction}
          href={eventHref(resident)}
          aria-label={`${actionLabel(resident)} for ${resident.displayLabel}`}
        >
          <span>{actionLabel(resident)}</span>
          <ArrowIcon />
        </Link>
      </div>
    </article>
  );
}

function WatchQueue({ residents }: Readonly<{ residents: ResidentOverviewItem[] }>) {
  return (
    <section className={styles.watchQueue} aria-labelledby="watch-queue-heading">
      <div className={styles.watchHeader}>
        <h3 id="watch-queue-heading">Remaining queue</h3>
      </div>
      <ol className={styles.watchList}>
        {residents.map((resident) => (
          <li key={resident.residentId} data-priority={resident.attention.priority}>
            <Link className={styles.watchResident} href={`/residents/${resident.residentId}`}>
              <span className={styles.watchName}>{resident.displayLabel}</span>
              <span>{resident.roomLabel}</span>
            </Link>
            <ResidentStatus axis="attention" value={resident.attention.priority} />
            <p>{resident.attention.headline}</p>
            <Link
              className={styles.watchAction}
              href={eventHref(resident)}
              aria-label={`${actionLabel(resident)} for ${resident.displayLabel}`}
            >
              <ArrowIcon />
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

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
        <Link href="/events">View event history <ArrowIcon /></Link>
      </section>
    );
  }

  const leadResident = attentionResidents[0];
  const queuedResidents = attentionResidents.slice(1);

  return (
    <section className={styles.attentionPanel} aria-labelledby="attention-heading">
      <header className={styles.panelHeader}>
        <div>
          <h2 id="attention-heading">Attention queue</h2>
          <p>Open items are ordered by urgency, with the next review first.</p>
        </div>
      </header>
      <div className={styles.attentionDesk}>
        <LeadSignal resident={leadResident} />
        {queuedResidents.length > 0 && <WatchQueue residents={queuedResidents} />}
      </div>
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
          <Button onClick={result.retry}>Retry</Button>
        </div>
      </section>
    );
  }

  if (result.items.length === 0) {
    return (
      <section className={styles.page}>
        <OverviewHeader residentCount={0} attentionCount={0} />
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
  const attentionCount = residents.filter((resident) => resident.attention.priority !== "none").length;

  return (
    <section className={styles.page}>
      <OverviewHeader residentCount={residents.length} attentionCount={attentionCount} />
      <OperationalSummary residents={residents} />
      <AttentionQueue residents={residents} />

      <section className={styles.residentSection} aria-labelledby="resident-sheet-heading">
        <div className={styles.sectionHeading}>
          <div>
            <h2 id="resident-sheet-heading">Resident inventory</h2>
            <p>Current attention, monitoring, device, and freshness status.</p>
          </div>
        </div>

        <div className={styles.grid}>
          <div className={styles.columnLabels} aria-hidden="true">
            <span>Resident / room</span>
            <span>Attention</span>
            <span>Monitoring</span>
            <span>Device</span>
            <span>Updated</span>
            <span />
          </div>
          {residents.map((resident) => <ResidentCard key={resident.residentId} resident={resident} />)}
        </div>
      </section>
    </section>
  );
}
