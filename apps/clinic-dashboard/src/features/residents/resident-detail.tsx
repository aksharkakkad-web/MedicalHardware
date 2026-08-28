"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ArrowIcon } from "@/components/icons/icons";
import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import { useMonitoringClient, type ResidentDetailResponse } from "@/lib/monitoring";

import styles from "./resident-detail.module.css";

const monitoringTone: Record<ResidentDetailResponse["resident"]["monitoring"]["state"], StatusTone> = { active: "healthy", limited: "attention", paused: "neutral", unavailable: "unavailable" };
const deviceTone: Record<ResidentDetailResponse["resident"]["device"]["status"], StatusTone> = { online: "healthy", degraded: "attention", offline: "critical", unknown: "unavailable" };

function formatTime(value: string) { return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }

export function ResidentDetail({ residentId }: { residentId: string }) {
  const client = useMonitoringClient();
  const [result, setResult] = useState<{ status: "loading" } | { status: "error" } | { status: "success"; data: ResidentDetailResponse }>({ status: "loading" });
  useEffect(() => { let current = true; client.getResident(residentId).then((data) => { if (current) setResult({ status: "success", data }); }).catch(() => { if (current) setResult({ status: "error" }); }); return () => { current = false; }; }, [client, residentId]);

  if (result.status === "loading") return <div className={styles.message} role="status">Loading resident workspace…</div>;
  if (result.status === "error") return <div className={styles.message} role="alert"><h1>Resident information is unavailable</h1><p>This does not mean monitoring is active or the resident is safe.</p><Link href="/">Return to overview</Link></div>;

  const { resident, events } = result.data;
  return <section className={styles.page}>
    <Link className={styles.back} href="/">← Clinic overview</Link>
    <header className={styles.header}><div><p>{resident.roomLabel}</p><h1>{resident.displayLabel}</h1><span>Assigned to this room in the synthetic clinic workspace</span></div><StatusPill label={resident.monitoring.state} tone={monitoringTone[resident.monitoring.state]} /></header>
    <div className={styles.layout}>
      <div className={styles.mainColumn}>
        <section className={styles.attention} data-priority={resident.attention.priority}><div><span>Current attention</span><h2>{resident.attention.headline}</h2><p>{resident.monitoring.reason}</p></div>{resident.attention.primaryEventId && <Link href={`/events/${resident.attention.primaryEventId}`}>Open event <ArrowIcon /></Link>}</section>
        <section className={styles.panel}><div className={styles.panelHeader}><h2>Event history</h2><span>{events.length} records</span></div>{events.length ? <div className={styles.events}>{events.map((event) => <Link href={`/events/${event.eventId}`} key={event.eventId}><span><strong>{event.headline}</strong><small>{formatTime(event.createdAt)} · {event.objectiveFamily}</small></span><StatusPill label={event.status} tone={event.status === "resolved" ? "healthy" : "attention"} /><ArrowIcon /></Link>)}</div> : <p className={styles.empty}>No event records are available for this resident.</p>}</section>
      </div>
      <aside className={styles.sideColumn}>
        <section className={styles.panel}><h2>Room assignment</h2><dl><div><dt>Room</dt><dd>{resident.roomLabel}</dd></div><div><dt>Assignment</dt><dd>{resident.assignmentStatus}</dd></div><div><dt>Resident record</dt><dd>{resident.displayLabel}</dd></div></dl></section>
        <section className={styles.panel}><div className={styles.panelHeader}><h2>Monitoring</h2><StatusPill label={resident.device.status} tone={deviceTone[resident.device.status]} /></div><dl><div><dt>State</dt><dd>{resident.monitoring.state}</dd></div><div><dt>Device</dt><dd>{resident.device.label}</dd></div><div><dt>Last update</dt><dd>{formatTime(resident.monitoring.lastUpdatedAt)}</dd></div></dl>{resident.monitoring.contextLabel && <p className={styles.context}>{resident.monitoring.contextLabel}</p>}</section>
      </aside>
    </div>
  </section>;
}
