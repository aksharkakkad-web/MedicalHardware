"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ArrowIcon, SearchIcon } from "@/components/icons/icons";
import { StatusPill, type StatusTone } from "@/components/status-pill/status-pill";
import { useMonitoringClient, type MonitoringEventDetail } from "@/lib/monitoring";

import styles from "./event-list.module.css";

type Filter = "active" | "all" | "resolved";

const statusTone: Record<MonitoringEventDetail["status"], StatusTone> = {
  detected: "attention", open: "critical", acknowledged: "attention", checked: "attention", resolved: "healthy",
};

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

export function EventList() {
  const client = useMonitoringClient();
  const [events, setEvents] = useState<MonitoringEventDetail[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [filter, setFilter] = useState<Filter>("active");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let current = true;
    client.listEvents().then((result) => { if (current) { setEvents(result.items); setStatus("success"); } }).catch(() => { if (current) setStatus("error"); });
    return () => { current = false; };
  }, [client]);

  const visible = useMemo(() => events.filter((event) => {
    const matchesFilter = filter === "all" || (filter === "resolved" ? event.status === "resolved" : event.status !== "resolved");
    const search = query.trim().toLowerCase();
    return matchesFilter && (!search || [event.headline, event.resident.displayLabel, event.resident.roomLabel, event.objectiveFamily].some((value) => value.toLowerCase().includes(search)));
  }), [events, filter, query]);

  const openCount = events.filter((event) => event.status !== "resolved").length;

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div><h1>Events</h1><p>Review current attention items and permanent event history.</p></div>
        {status === "success" && <span className={styles.count}>{openCount} active</span>}
      </header>

      <div className={styles.toolbar}>
        <div className={styles.filters} aria-label="Filter events">
          {(["active", "all", "resolved"] as const).map((item) => <button key={item} type="button" aria-pressed={filter === item} onClick={() => setFilter(item)}>{item[0].toUpperCase() + item.slice(1)}</button>)}
        </div>
        <label className={styles.search}><SearchIcon /><span className={styles.srOnly}>Search events</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search resident, room, or event" /></label>
      </div>

      {status === "loading" && <div className={styles.message} role="status">Loading event work…</div>}
      {status === "error" && <div className={styles.message} role="alert"><strong>Events are unavailable</strong><p>No safety conclusion can be made from this screen.</p></div>}
      {status === "success" && visible.length === 0 && <div className={styles.message} role="status"><strong>No events match this view</strong><p>Try another filter or clear the search.</p></div>}

      {status === "success" && visible.length > 0 && (
        <div className={styles.list}>
          <div className={styles.columnLabels} aria-hidden="true"><span>Event</span><span>Resident</span><span>Detected</span><span>Status</span><span /></div>
          {visible.map((event) => (
            <Link className={styles.row} href={`/events/${event.eventId}`} key={event.eventId}>
              <span className={styles.eventName}><span className={styles.priority} data-priority={event.priority} /> <span><strong>{event.headline}</strong><small>{event.objectiveFamily}{event.overdue ? " · Response overdue" : ""}</small></span></span>
              <span className={styles.resident}><strong>{event.resident.displayLabel}</strong><small>{event.resident.roomLabel}</small></span>
              <time dateTime={event.createdAt}>{formatTime(event.createdAt)}</time>
              <StatusPill label={event.status === "open" ? "Needs review" : event.status} tone={statusTone[event.status]} />
              <ArrowIcon className={styles.arrow} />
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
