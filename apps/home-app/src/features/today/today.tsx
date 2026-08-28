"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowIcon, CheckIcon, InfoIcon, RoutineIcon } from "@/components/icons";
import { useHomeMonitoringClient, type HomeOverviewResponse, type HomeTrend } from "@/lib/home-monitoring";
import styles from "./today.module.css";

function timeLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function Sparkline({ trend }: { trend: HomeTrend }) {
  if (!trend.points?.length) return <span className={styles.unavailable}>Not enough information yet</span>;
  const width = 112;
  const height = 32;
  const min = Math.min(...trend.points);
  const max = Math.max(...trend.points);
  const range = Math.max(max - min, 1);
  const points = trend.points.map((point, index) => `${(index / (trend.points!.length - 1)) * width},${height - 4 - ((point - min) / range) * (height - 8)}`).join(" ");
  return <svg className={styles.sparkline} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${trend.label} stayed close to its recent range`}><polyline points={points}/></svg>;
}

export function Today() {
  const client = useHomeMonitoringClient();
  const [overview, setOverview] = useState<HomeOverviewResponse | null>(null);
  const [error, setError] = useState(false);

  async function load() {
    setError(false);
    try { setOverview(await client.getOverview()); }
    catch { setError(true); }
  }

  useEffect(() => {
    let active = true;
    client.getOverview().then((response) => { if (active) setOverview(response); }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [client]);

  if (error) return <section className={styles.centerState} role="alert"><span className={styles.stateIcon}><InfoIcon/></span><h1>Today could not load</h1><p>The demo information is temporarily unavailable. Nothing has been guessed or filled in.</p><button onClick={() => void load()}>Try again</button></section>;
  if (!overview) return <section className={styles.centerState} role="status"><span className={styles.loadingDot}/><h1>Bringing today into view</h1><p>Gathering the latest demo update.</p></section>;

  const { lovedOne } = overview;
  return <div className={styles.page}>
    <header className={styles.intro}>
      <div><p className={styles.eyebrow}>Today · {lovedOne.displayLabel}</p><h1>A calm look at how things are going.</h1></div>
      <p className={styles.introNote}>Updated {timeLabel(lovedOne.status.lastUpdatedAt)}</p>
    </header>

    <section className={`${styles.statusWindow} ${styles[lovedOne.status.state]}`} aria-labelledby="status-heading">
      <div className={styles.statusGlyph}><CheckIcon/></div>
      <div className={styles.statusCopy}>
        <p className={styles.statusLabel}>Current picture</p>
        <h2 id="status-heading">{lovedOne.status.headline}</h2>
        <p>{lovedOne.status.summary}</p>
      </div>
      <aside className={styles.honestyNote}><InfoIcon/><span><strong>What this means</strong>This view notices meaningful changes. It does not promise that everything is okay.</span></aside>
    </section>

    <section className={styles.section} aria-labelledby="patterns-heading">
      <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>Recent patterns</p><h2 id="patterns-heading">The week at a glance</h2></div><span>Compared with their own routine</span></div>
      <div className={styles.trendSheet}>
        {lovedOne.trends.map((trend) => <article className={styles.trendRow} key={trend.trendId} data-testid="trend-row">
          <div className={styles.trendTitle}><span className={styles.trendDot}/><span>{trend.label}</span></div>
          <div className={styles.trendCopy}><h3>{trend.headline}</h3><p>{trend.summary}</p></div>
          <Sparkline trend={trend}/>
        </article>)}
      </div>
    </section>

    <div className={styles.lowerGrid}>
      <section className={styles.section} aria-labelledby="update-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>Important update</p><h2 id="update-heading">Worth knowing</h2></div></div>
        {lovedOne.importantUpdate ? <article className={styles.updateCard}>
          <div className={styles.updateMeta}><span>Important</span><time dateTime={lovedOne.importantUpdate.occurredAt}>Today, {timeLabel(lovedOne.importantUpdate.occurredAt)}</time></div>
          <h3>{lovedOne.importantUpdate.headline}</h3><p>{lovedOne.importantUpdate.summary}</p>
          <Link href={`/updates/${lovedOne.importantUpdate.eventId}`}>Understand this update <ArrowIcon/></Link>
        </article> : <div className={styles.emptyCard}><CheckIcon/><p>No important updates are waiting right now.</p></div>}
      </section>

      <section className={styles.section} aria-labelledby="activity-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>Recent activity</p><h2 id="activity-heading">What the day included</h2></div></div>
        <div className={styles.activityCard}>
          <ol>{lovedOne.recentActivity.map((item) => <li key={item.activityId}><span className={styles.activityDot}/><div><p>{item.label}</p><time dateTime={item.occurredAt}>{timeLabel(item.occurredAt)}</time></div></li>)}</ol>
          <Link href="/routines"><RoutineIcon/> Manage routines <ArrowIcon/></Link>
        </div>
      </section>
    </div>
  </div>;
}
