"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import {
  hasWorkspacePermission,
  useWorkspace,
  type ContextRecord,
  type ResidentMeasurement,
  type ResidentProfile,
  type WorkspaceSnapshot,
} from "@/lib/workspace";
import type { ResidentOverviewItem } from "@/lib/monitoring";
import {
  careTime,
  eventStateLabels,
  readingIsAvailable,
  residentName,
} from "./care-format";
import {
  CompletedFollowUpHistory,
  ConcernRow,
  HistoricalPriority,
  ResolvedConcernStatus,
  EmptyState,
  FollowUpList,
  PageHeading,
  PermissionNotice,
  WorkspaceState,
} from "./care-shared";
import { useConcernResponseDialog } from "./care-response-dialog";
import styles from "./care-workspace.module.css";

function Measurement({
  measurement,
  resident,
  snapshot,
}: {
  measurement: ResidentMeasurement;
  resident: ResidentOverviewItem;
  snapshot: WorkspaceSnapshot;
}) {
  const available = readingIsAvailable(measurement, resident);
  return (
    <div
      className={styles.measurement}
      data-kind={measurement.kind}
      data-available={available}
    >
      <h3>
        {measurement.label}
      </h3>
      {available ? (
        <div className={styles.reading}>
          {measurement.value}
          <small>{measurement.unit}</small>
        </div>
      ) : (
        <strong className={styles.unavailable}>Unavailable</strong>
      )}
      <p>
        {available
          ? `Observed ${careTime(measurement.observedAt, snapshot.facility.timeZone)}`
          : measurement.reason || resident.monitoring.reason}
      </p>
      {!available && <p>No resident-specific value shown</p>}
    </div>
  );
}
function ContextEditor({
  residentId,
  records,
}: {
  residentId: string;
  records: ContextRecord[];
}) {
  const { client, refresh, snapshot } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [target, setTarget] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!hasWorkspacePermission(snapshot, "report_context")) {
      setError(
        "This shared device is not permitted to report care context. Ask an administrator to review its permissions.",
      );
      return;
    }
    if (!text.trim()) {
      setError("Describe the information that needs review.");
      return;
    }
    setPending(true);
    setError("");
    setSaved("");
    try {
      await client.addContext(residentId, {
        category: "correction",
        text: text.trim(),
        ...(target ? { supersedesContextId: target } : {}),
      });
      await refresh();
      setText("");
      setOpen(false);
      setSaved(
        "Report saved in this demonstration. Review is still needed; approved context was not overwritten.",
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The report could not be confirmed. Your draft remains here.",
      );
    } finally {
      setPending(false);
    }
  }
  if (!hasWorkspacePermission(snapshot, "report_context"))
    return <PermissionNotice action="report care context" />;
  return (
    <>
      <Button
        variant="secondary"
        disabled={pending}
        onClick={() => {
          setOpen(!open);
          setSaved("");
        }}
      >
        Report context error
      </Button>
      {open && (
        <form
          className={styles.form}
          onSubmit={(e) => void submit(e)}
          style={{ marginTop: 16 }}
        >
          <FormField
            as="select"
            label="Information to review"
            disabled={pending}
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            options={[
              { value: "", label: "General correction" },
              ...records.map((record) => ({
                value: record.contextId,
                label: record.text.slice(0, 80),
              })),
            ]}
          />
          <FormField
            as="textarea"
            label="What needs correcting?"
            disabled={pending}
            hint="This report needs review. It does not replace approved care instructions."
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={1200}
          />
          <Button type="submit" pending={pending} pendingLabel="Saving report…">
            Save report for review
          </Button>
        </form>
      )}
      {error && (
        <p className={styles.actionError} role="alert">
          {error}
        </p>
      )}
      {saved && (
        <p className={styles.saved} role="status">
          {saved}
        </p>
      )}
    </>
  );
}
export function CareResidentDetail({ residentId }: { residentId: string }) {
  const { openResponse, responseDialog } = useConcernResponseDialog();
  const { snapshot, status } = useWorkspace();
  if (!snapshot || status === "error")
    return <WorkspaceState subject="Resident information" />;
  const resident = snapshot.residents.find((r) => r.residentId === residentId);
  const profile = snapshot.profiles.find((p) => p.residentId === residentId);
  if (!resident)
    return profile?.departedAt ? (
      <HistoricalResident profile={profile} snapshot={snapshot} />
    ) : (
      <WorkspaceState subject="Resident information" />
    );
  const contexts = snapshot.contexts.filter((c) => c.residentId === residentId);
  const events = snapshot.events.filter(
    (e) => e.resident.residentId === residentId,
  );
  const followUps = snapshot.followUps.filter(
    (f) => f.residentId === residentId && f.status !== "completed",
  );
  const measurements = snapshot.measurements.filter(
    (m) => m.residentId === residentId,
  );
  return (
    <div className={styles.page}>
      <Link className={styles.backLink} href="/residents">
        ← Residents & rooms
      </Link>
      <PageHeading
        title={residentName(
          snapshot.profiles,
          residentId,
          resident.displayLabel,
        )}
        eyebrow={`${resident.roomLabel} · ${snapshot.areas.find((a) => a.areaId === profile?.areaId)?.name ?? "Area unavailable"}`}
      />
      {events.some((event) => event.status !== "resolved") && (
        <section className={styles.residentOpenWork} aria-labelledby="resident-open-heading">
          <div className={styles.openWorkHeading}>
            <h2 id="resident-open-heading">Open concerns <span className={styles.count}>{events.filter((event) => event.status !== "resolved").length}</span></h2>
            <span className={styles.meta}>Staff review remains needed</span>
          </div>
          {events.filter((event) => event.status !== "resolved").map((event) => (
            <ConcernRow key={event.eventId} event={event} snapshot={snapshot} onRespond={() => openResponse(event.eventId)} />
          ))}
        </section>
      )}
      <div className={styles.layout}>
        <div className={styles.main}>
          <section
            className={styles.panel}
            aria-labelledby="measurements-heading"
          >
            <div className={styles.panelTitle}>
              <h2 id="measurements-heading" className={styles.iconHeading}>
                Last supplied measurements
              </h2>

            </div>
            <div className={styles.measurements}>
              {measurements.length ? (
                measurements.map((measurement) => (
                  <Measurement
                    key={measurement.kind}
                    measurement={measurement}
                    resident={resident}
                    snapshot={snapshot}
                  />
                ))
              ) : (
                <p className={styles.emptyCompact}>
                  Measurements are unavailable for this resident. No values have
                  been inferred.
                </p>
              )}
            </div>
            <p>
              Synthetic estimates at the stated observation times. They do not establish the resident’s present condition or safety.
            </p>
          </section>
          <section
            className={styles.panel}
            aria-labelledby="monitoring-heading"
          >
            <h2 id="monitoring-heading" className={styles.iconHeading}>

              Monitoring & coverage
            </h2>
            <dl className={styles.facts}>
              <div>
                <dt>Availability</dt>
                <dd>
                  <span
                    className={styles.stateDot}
                    data-state={resident.monitoring.state}
                  >
                    {resident.monitoring.state}
                  </span>
                </dd>
              </div>
              <div>
                <dt>Limitations</dt>
                <dd>{resident.monitoring.reason}</dd>
              </div>
              <div>
                <dt>Room assignment</dt>
                <dd>{resident.assignmentStatus}</dd>
              </div>
              <div>
                <dt>Last source update</dt>
                <dd>
                  {careTime(
                    resident.monitoring.lastUpdatedAt,
                    snapshot.facility.timeZone,
                  )}
                </dd>
              </div>
              <div>
                <dt>Room unit</dt>
                <dd>
                  {resident.device.label} · {resident.device.status}
                </dd>
              </div>
            </dl>
            <p>
              Historical measurements are not supplied by this demonstration
              service. No trend, average or continuous coverage has been
              inferred.
            </p>
            <p>
              <Link
                className={styles.textLink}
                href={`/residents/${residentId}/setup`}
              >
                Review monitoring setup →
              </Link>
            </p>
          </section>
          <section
            className={styles.panel}
            aria-labelledby="resident-concerns-heading"
          >
            <div className={styles.panelTitle}>
              <h2 id="resident-concerns-heading">
                Concern records
                <span className={styles.count}>{events.length}</span>
              </h2>
            </div>
            {events.length ? (
              <ul className={styles.plainList}>
                {events.map((event) => (
                  <li key={event.eventId}>
                    <h3>
                      <Link
                        className={styles.textLink}
                        href={`/events/${event.eventId}`}
                      >
                        {event.headline}
                      </Link>
                    </h3>
                    {event.status === "resolved" ? (
                      <div className={styles.recordDisposition}>
                        <ResolvedConcernStatus />
                        <HistoricalPriority priority={event.priority} />
                      </div>
                    ) : (
                      <p className={styles.meta}>
                        {event.priority} priority · {eventStateLabels[event.status]}
                      </p>
                    )}
                    <p className={styles.meta}>
                      Opened{" "}
                      {careTime(event.createdAt, snapshot.facility.timeZone)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No concerns returned">
                No matching event records are available. Monitoring availability
                remains a separate condition.
              </EmptyState>
            )}
          </section>
          <section
            className={styles.panel}
            aria-labelledby="resident-followup-heading"
          >
            <h2 id="resident-followup-heading">
              Outstanding follow-up
              <span className={styles.count}>{followUps.length}</span>
            </h2>
            {followUps.length ? (
              <FollowUpList items={followUps} snapshot={snapshot} editable />
            ) : (
              <p className={styles.emptyCompact}>
                No outstanding follow-up returned.
              </p>
            )}
            <CompletedFollowUpHistory
              items={snapshot.followUps.filter(
                (item) => item.residentId === residentId,
              )}
              snapshot={snapshot}
            />
          </section>
        </div>
        <aside className={styles.rail}>
          <section className={styles.panel} aria-labelledby="context-heading">
            <div className={styles.panelTitle}>
              <h2 id="context-heading" className={styles.iconHeading}>

                Care context
              </h2>
            </div>
            {contexts.length ? (
              <ul className={styles.contextList}>
                {contexts.map((context) => (
                  <li key={context.contextId}>
                    <div className={styles.contextTitle}>
                      <h3>
                        {
                          {
                            hospice: "Hospice context",
                            care_goal: "Comfort / care goal",
                            preference: "Resident preference",
                            observation: "Staff observation",
                            correction: "Correction reported",
                          }[context.category]
                        }
                      </h3>
                    </div>
                    <p>{context.text}</p>
                    <small>Source: {context.source}</small>
                    <small>
                      {careTime(context.recordedAt, snapshot.facility.timeZone)}{" "}
                      ·{" "}
                      {context.reviewStatus === "demo_reviewed"
                        ? "Reviewed in demonstration"
                        : "Needs review"}
                    </small>
                    {context.effectiveUntil && (
                      <small>
                        Effective until{" "}
                        {careTime(
                          context.effectiveUntil,
                          snapshot.facility.timeZone,
                        )}
                      </small>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.emptyCompact}>
                No source-backed context is supplied. Care goals and service
                contacts remain unknown.
              </p>
            )}
            <p className={styles.finePrint}>
              Hospice context does not by itself change or stop notifications.
              Follow the resident’s authorized care plan and facility procedure.
            </p>
            <div style={{ marginTop: 16 }}>
              <ContextEditor
                key={residentId}
                residentId={residentId}
                records={contexts}
              />
            </div>
          </section>
          <section className={styles.panel} aria-labelledby="identity-heading">
            <h2 id="identity-heading" className={styles.iconHeading}>

              Assignment details
            </h2>
            <dl className={styles.facts}>
              <div>
                <dt>Room</dt>
                <dd>{resident.roomLabel}</dd>
              </div>
              <div>
                <dt>Effective from</dt>
                <dd>
                  {careTime(
                    profile?.assignmentEffectiveAt ?? null,
                    snapshot.facility.timeZone,
                  )}
                </dd>
              </div>
              <div>
                <dt>Record</dt>
                <dd>{profile?.facilityResidentId ?? "Not supplied"}</dd>
              </div>
            </dl>
            <p>
              <Link
                className={styles.textLink}
                href={`/residents/${residentId}/settings`}
              >
                Context & notification settings →
              </Link>
            </p>
          </section>
        </aside>
      </div>
      {responseDialog}
    </div>
  );
}

function HistoricalResident({
  profile,
  snapshot,
}: {
  profile: ResidentProfile;
  snapshot: WorkspaceSnapshot;
}) {
  const events = snapshot.events.filter(
    (e) => e.resident.residentId === profile.residentId,
  );
  const contexts = snapshot.contexts.filter(
    (c) => c.residentId === profile.residentId,
  );
  const followUps = snapshot.followUps.filter(
    (f) => f.residentId === profile.residentId && f.status !== "completed",
  );
  return (
    <div className={styles.page}>
      <Link className={styles.backLink} href="/residents">
        ← Residents & rooms
      </Link>
      <PageHeading
        title={profile.name}
        eyebrow="Historical resident record"
        description={`Departure recorded ${careTime(profile.departedAt, snapshot.facility.timeZone)}`}
      />
      <div className={styles.resolved}>
        Current resident measurements are unavailable. This resident is no
        longer a current occupant; retained records keep their original
        attribution.
      </div>
      <div className={styles.layout}>
        <div className={styles.main}>
          <section className={styles.panel}>
            <h2>
              Concern history
              <span className={styles.count}>{events.length}</span>
            </h2>
            {events.length ? (
              <ul className={styles.plainList}>
                {events.map((event) => (
                  <li key={event.eventId}>
                    <h3>
                      <Link
                        className={styles.textLink}
                        href={`/events/${event.eventId}`}
                      >
                        {event.headline}
                      </Link>
                    </h3>
                    <p className={styles.meta}>
                      {eventStateLabels[event.status]} ·{" "}
                      {event.resident.roomLabel} at event
                    </p>
                    <p className={styles.meta}>
                      {careTime(event.createdAt, snapshot.facility.timeZone)}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.emptyCompact}>
                No retained concerns returned.
              </p>
            )}
          </section>
          <section className={styles.panel}>
            <h2>
              Outstanding follow-up
              <span className={styles.count}>{followUps.length}</span>
            </h2>
            {followUps.length ? (
              <FollowUpList items={followUps} snapshot={snapshot} editable />
            ) : (
              <p className={styles.emptyCompact}>
                No outstanding follow-up returned.
              </p>
            )}
            <CompletedFollowUpHistory
              items={snapshot.followUps.filter(
                (item) => item.residentId === profile.residentId,
              )}
              snapshot={snapshot}
            />
          </section>
        </div>
        <aside className={styles.rail}>
          <section className={styles.panel}>
            <h2>Retained care context</h2>
            {contexts.length ? (
              <ul className={styles.contextList}>
                {contexts.map((context) => (
                  <li key={context.contextId}>
                    <p>{context.text}</p>
                    <small>Source: {context.source}</small>
                    <small>
                      {careTime(context.recordedAt, snapshot.facility.timeZone)}{" "}
                      ·{" "}
                      {context.reviewStatus === "needs_review"
                        ? "Needs review"
                        : "Reviewed in demonstration"}
                    </small>
                    {context.effectiveUntil && (
                      <small>
                        Effective until{" "}
                        {careTime(
                          context.effectiveUntil,
                          snapshot.facility.timeZone,
                        )}
                      </small>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.emptyCompact}>
                No retained context returned.
              </p>
            )}
          </section>
          <section className={styles.panel}>
            <h2>Last recorded assignment</h2>
            <dl className={styles.facts}>
              <div>
                <dt>Room</dt>
                <dd>{profile.roomLabel}</dd>
              </div>
              <div>
                <dt>Effective from</dt>
                <dd>
                  {careTime(
                    profile.assignmentEffectiveAt,
                    snapshot.facility.timeZone,
                  )}
                </dd>
              </div>
              <div>
                <dt>Departed</dt>
                <dd>
                  {careTime(profile.departedAt, snapshot.facility.timeZone)}
                </dd>
              </div>
            </dl>
          </section>
        </aside>
      </div>
    </div>
  );
}
