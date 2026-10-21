"use client";

import Link from "next/link";
import { useState } from "react";
import { FormField } from "@/components/ui/form-field";
import { FacilityTimeField } from "@/components/ui/facility-time-field";
import { useWorkspace, type WorkspaceSnapshot } from "@/lib/workspace";
import {
  careTime,
  isCareInstant,
  concernQueue,
  residentName,
} from "./care-format";
import {
  ConcernRow,
  EmptyState,
  FollowUpList,
  PageHeading,
  WorkspaceState,
} from "./care-shared";
import styles from "./care-workspace.module.css";

export function CareHandover() {
  const { snapshot, status } = useWorkspace();
  if (!snapshot || status === "error")
    return <WorkspaceState subject="Handover" />;
  return <HandoverContent snapshot={snapshot} />;
}
function relativeStart(end: string, hours: number): string {
  return isCareInstant(end)
    ? new Date(Date.parse(end) - hours * 60 * 60 * 1000).toISOString()
    : "";
}
function HandoverContent({ snapshot }: { snapshot: WorkspaceSnapshot }) {
  const [hours, setHours] = useState("12");
  const [customStart, setStartTime] = useState(() =>
    relativeStart(snapshot.synchronizedAt, 12),
  );
  const [customEnd, setEndTime] = useState(snapshot.synchronizedAt);
  const endTime = hours === "custom" ? customEnd : snapshot.synchronizedAt;
  const startTime =
    hours === "custom" ? customStart : relativeStart(endTime, Number(hours));
  const validInterval =
    isCareInstant(startTime) &&
    isCareInstant(endTime) &&
    Date.parse(startTime) <= Date.parse(endTime);
  const intervalError =
    "Recent activity is unavailable until the interval has valid times, with the start before the end. Unresolved work remains visible.";
  const withinInterval = (time: string) =>
    validInterval &&
    Date.parse(time) >= Date.parse(startTime) &&
    Date.parse(time) <= Date.parse(endTime);
  function choosePreset(value: string) {
    if (value === "custom" && hours !== "custom") {
      setStartTime(startTime);
      setEndTime(endTime);
    }
    setHours(value);
  }
  const unresolved = concernQueue(snapshot.events, snapshot.profiles, "all");
  const followUps = snapshot.followUps
    .filter((f) => f.status !== "completed")
    .sort(
      (a, b) =>
        (a.dueAt ? Date.parse(a.dueAt) : Infinity) -
        (b.dueAt ? Date.parse(b.dueAt) : Infinity),
    );
  const gaps = snapshot.residents.filter(
    (r) => r.monitoring.state !== "active" || r.assignmentStatus !== "active",
  );
  const contexts = snapshot.contexts.filter((c) =>
    withinInterval(c.recordedAt),
  );
  const checks = snapshot.checks.filter((c) => withinInterval(c.recordedAt));
  const transfers = snapshot.assignmentHistory.filter((a) =>
    withinInterval(a.recordedAt),
  );
  const recentResolved = snapshot.events.filter(
    (e) =>
      e.status === "resolved" &&
      e.actionHistory.some(
        (h) => h.action === "resolved" && withinInterval(h.occurredAt),
      ),
  );
  const changes =
    contexts.length + checks.length + transfers.length + recentResolved.length;
  return (
    <div className={styles.page}>
      <PageHeading
        title="Shift handover"
        description="Outstanding care work and the records to carry forward."
        eyebrow={`${snapshot.currentClient.name} · authorized coverage`}
      />
      <div className={styles.interval}>
        <FormField
          as="select"
          label="Recent activity interval"
          value={hours}
          onChange={(e) => choosePreset(e.target.value)}
          options={[
            { value: "8", label: "Last 8 hours" },
            { value: "12", label: "Last 12 hours" },
            { value: "24", label: "Last 24 hours" },
            { value: "custom", label: "Custom interval" },
          ]}
        />
        <FacilityTimeField
          label="Interval start"
          value={startTime}
          onChange={(value) => {
            setEndTime(endTime);
            setHours("custom");
            setStartTime(value);
          }}
          timeZone={snapshot.facility.timeZone}
          required
        />
        <FacilityTimeField
          label="Interval end"
          value={endTime}
          onChange={(value) => {
            setStartTime(startTime);
            setHours("custom");
            setEndTime(value);
          }}
          timeZone={snapshot.facility.timeZone}
          required
        />
        <p className={styles.meta}>
          {validInterval
            ? `${careTime(startTime, snapshot.facility.timeZone)} – ${careTime(endTime, snapshot.facility.timeZone)}`
            : "Interval needs review"}
          <br />
          Facility time zone: {snapshot.facility.timeZone}
        </p>
      </div>
      <div className={styles.scope}>
        <div>
          <strong>
            Unresolved work carries forward regardless of when it started.
          </strong>
          <p>
            The interval applies to recent activity. Monitoring gaps below
            describe the current snapshot; historical coverage is not supplied.
            No live synchronization or background alert delivery is connected.
          </p>
        </div>
      </div>
      <div className={styles.stats}>
        <span>
          <strong>{unresolved.length}</strong> unresolved concerns
        </span>
        <span>
          <strong>{followUps.length}</strong> outstanding follow-ups
        </span>
        <span>
          <strong>{gaps.length}</strong> monitoring limitations
        </span>
        <span>
          {validInterval ? (
            <>
              <strong>{changes}</strong> activity records in interval
            </>
          ) : (
            "Activity count unavailable"
          )}
        </span>
      </div>
      <section
        className={styles.section}
        role="region"
        aria-labelledby="handover-concerns"
      >
        <div className={styles.sectionHeading}>
          <div>
            <h2 id="handover-concerns">
              Unresolved concerns
              <span className={styles.count}>{unresolved.length}</span>
            </h2>
            <p>
              Includes analysis pending, unacknowledged work and recorded checks
              that remain open.
            </p>
          </div>
        </div>
        {unresolved.length ? (
          <div className={styles.concernList}>
            {unresolved.map((event) => (
              <ConcernRow
                key={event.eventId}
                event={event}
                snapshot={snapshot}
              />
            ))}
          </div>
        ) : (
          <EmptyState title="No unresolved concerns returned">
            This is a statement about available records, not proof of complete
            monitoring or safety.
          </EmptyState>
        )}
      </section>
      <div className={styles.handoverGrid}>
        <section className={styles.panel} aria-labelledby="handover-followup">
          <h2 id="handover-followup">
            Follow-up to carry forward
            <span className={styles.count}>{followUps.length}</span>
          </h2>
          <p>
            Completing a follow-up does not itself resolve its concern. A
            handed-over item remains outstanding.
          </p>
          {followUps.length ? (
            <FollowUpList items={followUps} snapshot={snapshot} editable />
          ) : (
            <p className={styles.emptyCompact}>
              No outstanding follow-up returned.
            </p>
          )}
        </section>
        <section className={styles.panel} aria-labelledby="handover-gaps">
          <h2 id="handover-gaps">
            Monitoring & delivery gaps
            <span className={styles.count}>{gaps.length}</span>
          </h2>
          <p>
            Availability problems are separate from resident-facing priority.
          </p>
          <ul className={styles.plainList}>
            {gaps.map((resident) => (
              <li key={resident.residentId}>
                <h3>
                  <Link
                    className={styles.textLink}
                    href={`/residents/${resident.residentId}`}
                  >
                    {residentName(
                      snapshot.profiles,
                      resident.residentId,
                      resident.displayLabel,
                    )}{" "}
                    · {resident.roomLabel}
                  </Link>
                </h3>
                <p>{resident.monitoring.reason}</p>
                <p className={styles.meta}>
                  Updated{" "}
                  {careTime(
                    resident.monitoring.lastUpdatedAt,
                    snapshot.facility.timeZone,
                  )}
                </p>
              </li>
            ))}
          </ul>
          {gaps.length === 0 && (
            <p className={styles.emptyCompact}>
              No monitoring limitations returned in this snapshot.
            </p>
          )}
          <div className={styles.resolved} style={{ marginTop: 20 }}>
            <strong>Alert delivery is not connected.</strong>
            <p>
              This demonstration cannot establish unattended notification
              coverage.{" "}
              <Link className={styles.textLink} href="/notifications">
                Review notification readiness
              </Link>
              .
            </p>
          </div>
        </section>
      </div>
      <section className={styles.panel} aria-labelledby="handover-changes">
        <h2 id="handover-changes">
          Recent activity
          {validInterval && <span className={styles.count}>{changes}</span>}
        </h2>
        <p>
          Source records saved in the selected interval. These records are not a
          generated clinical summary.
        </p>
        {!validInterval ? (
          <p className={styles.actionError} role="alert">
            {intervalError}
          </p>
        ) : changes ? (
          <ul className={styles.plainList}>
            {checks.map((check) => (
              <li key={check.checkId}>
                <h3>
                  Outcome recorded ·{" "}
                  {residentName(
                    snapshot.profiles,
                    check.residentId,
                    "Resident record",
                  )}
                </h3>
                <p>
                  {check.completedCheck
                    ? "Resident check recorded"
                    : "No completed check recorded"}{" "}
                  · {check.clientLabel}
                </p>
                <p className={styles.meta}>
                  {careTime(check.recordedAt, snapshot.facility.timeZone)}
                </p>
                <Link
                  className={styles.textLink}
                  href={`/events/${check.eventId}`}
                >
                  Review response record
                </Link>
              </li>
            ))}
            {contexts.map((context) => (
              <li key={context.contextId}>
                <h3>
                  Context{" "}
                  {context.reviewStatus === "needs_review"
                    ? "awaits review"
                    : "recorded"}{" "}
                  ·{" "}
                  {residentName(
                    snapshot.profiles,
                    context.residentId,
                    "Resident record",
                  )}
                </h3>
                <p>{context.text}</p>
                <p className={styles.meta}>
                  {context.source} ·{" "}
                  {careTime(context.recordedAt, snapshot.facility.timeZone)}
                </p>
                <Link
                  className={styles.textLink}
                  href={`/residents/${context.residentId}`}
                >
                  Review care context
                </Link>
              </li>
            ))}
            {transfers.map((transfer, i) => (
              <li key={`${transfer.residentId}-${transfer.recordedAt}-${i}`}>
                <h3>
                  Assignment change ·{" "}
                  {residentName(
                    snapshot.profiles,
                    transfer.residentId,
                    "Resident record",
                  )}
                </h3>
                <p className={styles.meta}>
                  Effective{" "}
                  {careTime(transfer.effectiveAt, snapshot.facility.timeZone)}
                </p>
                <Link
                  className={styles.textLink}
                  href={`/residents/${transfer.residentId}`}
                >
                  Review assignment
                </Link>
              </li>
            ))}
            {recentResolved.map((event) => (
              <li key={event.eventId}>
                <h3>
                  Concern resolved ·{" "}
                  {residentName(
                    snapshot.profiles,
                    event.resident.residentId,
                    event.resident.displayLabel,
                  )}
                </h3>
                <p>{event.headline}</p>
                <Link
                  className={styles.textLink}
                  href={`/events/${event.eventId}`}
                >
                  Review resolved history
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.emptyCompact}>
            No recent activity records were returned for this interval. This
            does not establish that the period had complete observation.
          </p>
        )}
      </section>
      <p className={styles.finePrint}>
        Use the facility’s handover procedure to confirm who will carry work
        forward. No personal staff identity is verified by this shared station.
      </p>
    </div>
  );
}
