"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ArrowIcon, SearchIcon } from "@/components/icons/icons";
import { StatusPill } from "@/components/status-pill/status-pill";
import { useMonitoringClient, type ClinicDevice } from "@/lib/monitoring";

import { deviceStatusPresentation, formatTimestamp, setupLabel } from "./device-format";
import styles from "./device-list.module.css";

type Filter = "all" | "attention" | "online" | "unassigned";

function needsAttention(device: ClinicDevice): boolean {
  return !["online"].includes(device.health.status) || device.setup.state === "needs_attention";
}

export function DeviceList() {
  const client = useMonitoringClient();
  const [devices, setDevices] = useState<ClinicDevice[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    let current = true;
    client.listDevices()
      .then((result) => {
        if (current) {
          setDevices(result.items);
          setStatus("success");
        }
      })
      .catch(() => {
        if (current) setStatus("error");
      });
    return () => { current = false; };
  }, [client, requestKey]);

  const visible = useMemo(() => devices.filter((device) => {
    const matchesFilter = filter === "all"
      || (filter === "attention" && needsAttention(device))
      || (filter === "online" && device.health.status === "online")
      || (filter === "unassigned" && device.assignmentStatus === "unassigned");
    const search = query.trim().toLowerCase();
    const matchesSearch = !search || [
      device.displayLabel,
      device.modelLabel,
      device.roomLabel ?? "",
      device.residentLabel ?? "",
    ].some((value) => value.toLowerCase().includes(search));
    return matchesFilter && matchesSearch;
  }), [devices, filter, query]);

  const attentionCount = devices.filter(needsAttention).length;

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1>Devices</h1>
          <p>See which room hubs are healthy, limited, offline, or waiting for setup.</p>
        </div>
        {status === "success" && (
          <div className={styles.summary} aria-label={`${attentionCount} devices need attention`}>
            <strong>{attentionCount}</strong>
            <span>need attention</span>
          </div>
        )}
      </header>

      <div className={styles.toolbar}>
        <div className={styles.filters} aria-label="Filter devices">
          {(["all", "attention", "online", "unassigned"] as const).map((item) => (
            <button key={item} type="button" aria-pressed={filter === item} onClick={() => setFilter(item)}>
              {{ all: "All", attention: "Needs attention", online: "Online", unassigned: "Unassigned" }[item]}
            </button>
          ))}
        </div>
        <label className={styles.search}>
          <SearchIcon />
          <span className={styles.srOnly}>Search devices</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search device, room, or resident" />
        </label>
      </div>

      {status === "loading" && <div className={styles.message} role="status">Loading device inventory…</div>}
      {status === "error" && <div className={styles.message} role="alert"><strong>Device information is unavailable</strong><p>Monitoring availability cannot be confirmed from this screen.</p><button type="button" onClick={() => { setStatus("loading"); setRequestKey((value) => value + 1); }}>Try again</button></div>}
      {status === "success" && visible.length === 0 && <div className={styles.message} role="status"><strong>No devices match this view</strong><p>Try another filter or clear the search.</p></div>}

      {status === "success" && visible.length > 0 && (
        <div className={styles.list}>
          <div className={styles.columnLabels} aria-hidden="true">
            <span>Device</span><span>Assignment</span><span>Health</span><span>Last update</span><span>Setup</span><span />
          </div>
          {visible.map((device) => {
            const health = deviceStatusPresentation[device.health.status];
            return (
              <Link className={styles.row} href={`/devices/${device.deviceId}`} key={device.deviceId}>
                <span className={styles.deviceName}>
                  <span className={styles.srOnly}>Device: </span>
                  <span className={styles.deviceGlyph} data-status={device.health.status} aria-hidden="true"><span /></span>
                  <span><strong>{device.displayLabel}</strong><small>{device.modelLabel}</small></span>
                </span>
                <span className={styles.assignment}>
                  <span className={styles.srOnly}>Assignment: </span>
                  <strong>{device.roomLabel ?? "No room assigned"}</strong>
                  <small>{device.residentLabel ?? "No resident assigned"}</small>
                </span>
                <span className={styles.health}><span className={styles.srOnly}>Health: </span><StatusPill label={health.label} tone={health.tone} /><small>{device.health.summary}</small></span>
                <time dateTime={device.health.lastSeenAt ?? undefined}><span className={styles.srOnly}>Last update: </span>{formatTimestamp(device.health.lastSeenAt)}</time>
                <span className={styles.setup}><span className={styles.srOnly}>Setup: </span><strong>Version {device.setup.version}</strong><small>{setupLabel(device.setup.state)}</small></span>
                <ArrowIcon className={styles.arrow} />
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
