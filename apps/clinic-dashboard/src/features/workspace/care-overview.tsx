"use client";

import Link from "next/link";
import { useState } from "react";
import { FormField } from "@/components/ui/form-field";
import { SearchIcon } from "@/components/icons/icons";
import { useWorkspace, type WorkspaceSnapshot } from "@/lib/workspace";
import {
  careTime,
  concernQueue,
  eventStateLabels,
  readingIsAvailable,
  residentName,
} from "./care-format";
import {
  ConcernRow,
  EmptyState,
  PageHeading,
  ScopeNote,
  WorkspaceState,
} from "./care-shared";
import styles from "./care-workspace.module.css";

export function ResidentRoster({ snapshot }: { snapshot: WorkspaceSnapshot }) {
  const [search, setSearch] = useState("");
  const [monitoring, setMonitoring] = useState("all");
  const inArea = snapshot.residents.filter(
    (r) =>
      snapshot.currentAreaId === "all" ||
      snapshot.profiles.some(
        (p) =>
          p.residentId === r.residentId && p.areaId === snapshot.currentAreaId,
      ),
  );
  const rows = inArea.filter((r) => {
    const name = residentName(snapshot.profiles, r.residentId, r.displayLabel);
    return (
      `${name} ${r.roomLabel}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()) &&
      (monitoring === "all" ||
        (monitoring === "gaps"
          ? r.monitoring.state !== "active"
          : r.monitoring.state === monitoring))
    );
  });
  return (
    <div className={styles.roster}>
      <div className={styles.toolbar}>
        <div className={styles.searchControl}>
          <SearchIcon />
          <FormField
            className={styles.search}
            label="Find a resident or room"
            type="search"
            placeholder="Search name or room…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <FormField
          className={styles.filter}
          as="select"
          label="Monitoring"
          value={monitoring}
          onChange={(e) => setMonitoring(e.target.value)}
          options={[
            { value: "all", label: "All monitoring states" },
            { value: "active", label: "Active monitoring" },
            { value: "gaps", label: "Gaps or limitations" },
          ]}
        />
        <span className={styles.resultCount}>
          {rows.length} of {inArea.length} residents
        </span>
      </div>
      {rows.length ? (
        <table
          className={styles.table}
          aria-label="Residents in the selected area"
        >
          <thead>
            <tr>
              <th>Room / resident</th>
              <th>Monitoring</th>
              <th>Last supplied estimates</th>
              <th>Open work</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((resident) => {
              const measurements = snapshot.measurements.filter(
                (m) => m.residentId === resident.residentId,
              );
              const available = measurements.filter((m) =>
                readingIsAvailable(m, resident),
              );
              const open = snapshot.events.filter(
                (e) =>
                  e.resident.residentId === resident.residentId &&
                  e.status !== "resolved",
              );
              return (
                <tr key={resident.residentId}>
                  <td>
                    <Link
                      className={styles.residentLink}
                      href={`/residents/${resident.residentId}`}
                    >
                      <span className={styles.residentIdentity}>
                        <strong>{resident.roomLabel}</strong>
                        <span>{residentName(snapshot.profiles, resident.residentId, resident.displayLabel)}</span>
                      </span>
                    </Link>
                  </td>
                  <td data-label="Monitoring">
                    <span
                      className={styles.stateDot}
                      data-state={resident.monitoring.state}
                    >
                      {resident.monitoring.state[0].toUpperCase() +
                        resident.monitoring.state.slice(1)}
                    </span>
                    <p className={styles.meta}>
                      {resident.monitoring.contextLabel ??
                        resident.monitoring.reason}
                    </p>
                  </td>
                  <td data-label="Estimates">
                    {available.length ? (
                      <>
                        <span className={styles.mono}>
                          {available
                            .map((m) => `${m.value} ${m.unit}`)
                            .join(" · ")}
                        </span>
                        <p className={styles.meta}>
                          Observed{" "}
                          {careTime(
                            available[0].observedAt,
                            snapshot.facility.timeZone,
                          )}
                        </p>
                      </>
                    ) : (
                      <>
                        <span>Unavailable</span>
                        <p className={styles.meta}>No attributed reading</p>
                      </>
                    )}
                  </td>
                  <td data-label="Open work">
                    {open.length ? (
                      <>
                        <strong>
                          {open.length}{" "}
                          {open.length === 1 ? "concern" : "concerns"}
                        </strong>
                        <p className={styles.meta}>
                          {eventStateLabels[open[0].status]}
                        </p>
                      </>
                    ) : (
                      <>
                        <span>No open concerns</span>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <EmptyState title="No residents match">
          Try a different name, room or monitoring filter. Filters do not change
          the underlying concern records.
        </EmptyState>
      )}
      <p className={styles.finePrint}>
        Readings and the absence of a concern do not establish resident safety.
      </p>
    </div>
  );
}
export function CareOverview() {
  const { snapshot, status } = useWorkspace();
  if (!snapshot || status === "error") return <WorkspaceState />;
  const queue = concernQueue(
    snapshot.events,
    snapshot.profiles,
    snapshot.currentAreaId,
  );
  const unanswered = queue.filter(
    (e) => e.status === "open" || e.status === "detected",
  ).length;
  const gapCount = snapshot.residents.filter(
    (r) => r.monitoring.state !== "active",
  ).length;
  return (
    <div className={styles.page}>
      <PageHeading title="Care overview">
        <Link className={styles.textLink} href="/handover">
          Open handover →
        </Link>
      </PageHeading>
      <ScopeNote snapshot={snapshot} />
      <section
        className={`${styles.section} ${styles.attentionSurface}`}
        aria-labelledby="attention-heading"
      >
        <div className={styles.sectionHeading}>
          <div className={styles.sectionLead}>
            <div>
              <h2 id="attention-heading">
                Needs attention
                <span className={styles.count}>{queue.length}</span>
              </h2>
              <div className={styles.stats}>
                <span><strong>{unanswered}</strong> unacknowledged</span>
                <span><strong>{queue.length - unanswered}</strong> seen or checked</span>
                <span><strong>{snapshot.followUps.filter((f) => f.status !== "completed").length}</strong> follow-ups outstanding</span>
              </div>
            </div>
          </div>
          <Link className={styles.textLink} href="/events">
            All concerns
          </Link>
        </div>
        {queue.length ? (
          <div className={styles.concernList}>
            {queue.map((event) => (
              <ConcernRow
                key={event.eventId}
                event={event}
                snapshot={snapshot}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="No unresolved concerns returned">
            This describes the available event records. It does not establish
            complete monitoring or resident safety.
          </EmptyState>
        )}
      </section>
      <section className={styles.section} aria-labelledby="roster-heading">
        <div className={styles.sectionHeading}>
          <div className={styles.sectionLead}>
            <div>
              <h2 id="roster-heading">Residents & rooms</h2>
              <p>
                {gapCount} {gapCount === 1 ? "resident has" : "residents have"}{" "}
                monitoring gaps or limitations in covered areas. Monitoring
                availability is separate from resident risk.
              </p>
            </div>
          </div>
        </div>
        <ResidentRoster snapshot={snapshot} />
      </section>
      <p className={styles.finePrint}>
        Source observations{" "}
        {careTime(snapshot.sourceObservedAt, snapshot.facility.timeZone)} ·
        Workspace refreshed{" "}
        {careTime(snapshot.synchronizedAt, snapshot.facility.timeZone)}.
        Synthetic estimates are not live readings.
      </p>
    </div>
  );
}
export function CareResidentDirectory() {
  const { snapshot, status } = useWorkspace();
  if (!snapshot || status === "error")
    return <WorkspaceState subject="Resident directory" />;
  return (
    <div className={styles.page}>
      <PageHeading
        title="Residents & rooms"
        description="Find an assigned resident, review monitoring and open the care record."
      />
      <ScopeNote snapshot={snapshot} />
      <ResidentRoster snapshot={snapshot} />
    </div>
  );
}
export function CareEvents() {
  const { snapshot, status } = useWorkspace();
  const [tab, setTab] = useState("active");
  if (!snapshot || status === "error")
    return <WorkspaceState subject="Concern records" />;
  const active = concernQueue(
    snapshot.events,
    snapshot.profiles,
    snapshot.currentAreaId,
  );
  const history = snapshot.events.filter((e) => e.status === "resolved");
  const items = tab === "active" ? active : history;
  return (
    <div className={styles.page}>
      <PageHeading
        title="Concerns"
        description="Active care work and permanent resolved history."
      />
      <div className={styles.eventTabs} role="group" aria-label="Show concerns">
        <button type="button" aria-pressed={tab === "active"} onClick={() => setTab("active")}>
          Unresolved <span>{active.length}</span>
        </button>
        <button type="button" aria-pressed={tab === "history"} onClick={() => setTab("history")}>
          Resolved history <span>{history.length}</span>
        </button>
      </div>
      {items.length ? (
        <div className={styles.concernList}>
          {items.map((event) => (
            <ConcernRow key={event.eventId} event={event} snapshot={snapshot} />
          ))}
        </div>
      ) : (
        <EmptyState title="No matching concerns">
          No records were returned for this view. Check monitoring coverage
          separately.
        </EmptyState>
      )}
    </div>
  );
}
