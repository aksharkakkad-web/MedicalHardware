"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ChevronLeftIcon, SignalIcon } from "@/components/icons/icons";
import { StatusPill } from "@/components/status-pill/status-pill";
import { useMonitoringClient, type ClinicDeviceDetailResponse } from "@/lib/monitoring";

import { availabilityLabel, deviceStatusPresentation, formatTimestamp, setupLabel, sourceStatusLabel, sourceTone } from "./device-format";
import styles from "./device-detail.module.css";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; data: ClinicDeviceDetailResponse };

function nextStep(device: ClinicDeviceDetailResponse["device"]): { title: string; body: string } {
  if (device.assignmentStatus !== "assigned") {
    return { title: "Assign this device", body: "Choose one monitored room and confirm its assigned resident before starting setup." };
  }
  if (device.health.status === "offline") {
    return { title: "Check the room hub", body: "Confirm power and network access in the room. Current resident monitoring is unavailable." };
  }
  if (device.health.status === "degraded") {
    return { title: "Review source limitations", body: "Check the limited sensing sources and the room setup before trusting resident-specific output." };
  }
  if (device.health.status === "buffering" || device.health.status === "retrying") {
    return { title: "Watch delivery recovery", body: "The device is preserving recent packages while it retries delivery. Check again if this continues." };
  }
  return { title: "No device action needed", body: "The device is reporting normally. Continue routine monitoring from the clinic overview." };
}

export function DeviceDetail({ deviceId }: Readonly<{ deviceId: string }>) {
  const client = useMonitoringClient();
  const [result, setResult] = useState<LoadState>({ status: "loading" });
  const [requestKey, setRequestKey] = useState(0);

  useEffect(() => {
    let current = true;
    client.getDevice(deviceId)
      .then((data) => { if (current) setResult({ status: "success", data }); })
      .catch(() => { if (current) setResult({ status: "error" }); });
    return () => { current = false; };
  }, [client, deviceId, requestKey]);

  if (result.status === "loading") return <div className={styles.message} role="status">Opening device workspace…</div>;
  if (result.status === "error") return <div className={styles.message} role="alert"><h1>Device information is unavailable</h1><p>This screen cannot confirm whether monitoring is active.</p><div className={styles.messageActions}><button type="button" onClick={() => { setResult({ status: "loading" }); setRequestKey((value) => value + 1); }}>Try again</button><Link href="/devices">Return to devices</Link></div></div>;

  const { device } = result.data;
  const health = deviceStatusPresentation[device.health.status];
  const action = nextStep(device);

  return (
    <section className={styles.page}>
      <Link className={styles.back} href="/devices"><ChevronLeftIcon />All devices</Link>
      <header className={styles.header}>
        <div>
          <div className={styles.titleLine}><h1>{device.displayLabel}</h1><StatusPill label={health.label} tone={health.tone} /></div>
          <p>{device.modelLabel} · {device.roomLabel ?? "Not assigned to a room"}</p>
        </div>
        <span className={styles.lastUpdate}>Last update<br /><strong>{formatTimestamp(device.health.lastSeenAt)}</strong></span>
      </header>

      <div className={styles.notice} data-tone={health.tone}>
        <span className={styles.noticeMark} aria-hidden="true" />
        <div><strong>{availabilityLabel(device.health.dataAvailability)} monitoring data</strong><p>{device.health.summary}</p></div>
      </div>

      <div className={styles.layout}>
        <div className={styles.primary}>
          <section className={styles.panel} aria-labelledby="sources-heading">
            <div className={styles.panelHeader}>
              <div><h2 id="sources-heading">Sensing sources</h2><p>Each source is shown separately so one healthy signal cannot hide another source’s problem.</p></div>
              <SignalIcon />
            </div>
            <div className={styles.sourceList}>
              {device.sources.map((source) => (
                <div className={styles.sourceRow} key={source.sourceId}>
                  <div><strong>{source.label}</strong><p>{source.detail}</p></div>
                  <div className={styles.sourceState}><StatusPill label={sourceStatusLabel[source.status]} tone={sourceTone[source.status]} /><time dateTime={source.lastSeenAt ?? undefined}>{formatTimestamp(source.lastSeenAt)}</time></div>
                </div>
              ))}
            </div>
          </section>

        </div>

        <aside className={styles.sidebar}>
          <section className={styles.panel}>
            <h2>Assignment</h2>
            <dl className={styles.facts}>
              <div><dt>Room</dt><dd>{device.roomLabel ?? "Not assigned"}</dd></div>
              <div><dt>Resident</dt><dd>{device.residentLabel ?? "Not assigned"}</dd></div>
              <div><dt>Status</dt><dd>{device.assignmentStatus}</dd></div>
            </dl>
          </section>
          <section className={styles.panel}>
            <h2>Monitoring setup</h2>
            <dl className={styles.facts}>
              <div><dt>Setup version</dt><dd>{device.setup.version || "Not started"}</dd></div>
              <div><dt>Readiness</dt><dd>{setupLabel(device.setup.state)}</dd></div>
              <div><dt>Last changed</dt><dd>{formatTimestamp(device.setup.updatedAt)}</dd></div>
            </dl>
          </section>
          <section className={styles.nextStep} data-tone={health.tone}>
            <span>Recommended next step</span>
            <h2>{action.title}</h2>
            <p>{action.body}</p>
          </section>
        </aside>
      </div>
    </section>
  );
}
