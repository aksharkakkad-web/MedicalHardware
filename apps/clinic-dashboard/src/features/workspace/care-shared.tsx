"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { FormField } from "@/components/ui/form-field";
import { Button } from "@/components/ui/button";
import { AlertIcon, ArrowIcon, SignalIcon } from "@/components/icons/icons";
import type { MonitoringEventDetail } from "@/lib/monitoring";
import {
  hasWorkspacePermission,
  useWorkspace,
  type FollowUp,
  type WorkspaceSnapshot,
} from "@/lib/workspace";
import {
  careTime,
  eventStateLabels,
  outcomeLabels,
  residentName,
} from "./care-format";
import styles from "./care-workspace.module.css";

export function PermissionNotice({ action }: { action: string }) {
  return (
    <p className={styles.finePrint}>
      This shared device can view this record but is not permitted to {action}.
      Ask an administrator to review its permissions.
    </p>
  );
}

export function WorkspaceState({
  subject = "Care workspace",
}: {
  subject?: string;
}) {
  const { status, error, refresh } = useWorkspace();
  if (status === "loading")
    return (
      <div className={styles.loading} role="status">
        <p>Loading {subject.toLowerCase()}…</p>
        <div className={styles.loadingLine} />
        <div className={styles.loadingLine} />
        <p className={styles.meta}>
          Getting the available records for this shared station.
        </p>
      </div>
    );
  return (
    <section className={styles.error} role="alert">
      <h1>{subject} is unavailable</h1>
      <p>
        {error ??
          "The requested record is outside this station’s coverage or is no longer available."}{" "}
        This does not establish that a concern has ended. Use the facility’s
        downtime procedure if a response is needed.
      </p>
      <Button onClick={() => void refresh()}>Try again</Button>
    </section>
  );
}
export function PageHeading({
  title,
  description,
  eyebrow,
  children,
}: {
  title: string;
  description?: string;
  eyebrow?: string;
  children?: ReactNode;
}) {
  return (
    <header className={styles.heading}>
      <div>
        {eyebrow && <span className={styles.eyebrow}>{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {children}
    </header>
  );
}
export function ScopeNote({ snapshot }: { snapshot: WorkspaceSnapshot }) {
  const coverage = snapshot.areas
    .filter((area) => snapshot.currentClient.areaIds.includes(area.areaId))
    .map((area) => area.name)
    .join(", ");
  return (
    <div className={styles.scope}>
      <SignalIcon className={styles.scopeIcon} />
      <div>
        <strong>
          {snapshot.currentClient.name} covers {coverage || "no approved areas"}
          .
        </strong>
        {snapshot.currentAreaId !== "all" && (
          <p>
            High and critical work across this station’s coverage stays visible
            when the view is narrowed.
          </p>
        )}
      </div>
      <Link className={styles.scopeLink} href="/notifications">
        Review alert coverage
      </Link>
    </div>
  );
}
export function EmptyState({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={styles.empty}>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function ConcernRow({
  event,
  snapshot,
}: {
  event: MonitoringEventDetail;
  snapshot: WorkspaceSnapshot;
}) {
  const checks = snapshot.checks.filter(
    (check) => check.eventId === event.eventId,
  );
  const latest = checks[checks.length - 1];
  const actor =
    latest?.clientLabel ??
    event.actionHistory.filter((item) => item.action !== "opened").at(-1)
      ?.actorLabel;
  const selectedArea = snapshot.profiles.find(
    (p) => p.residentId === event.resident.residentId,
  )?.areaId;
  const outsideSelected =
    snapshot.currentAreaId !== "all" && selectedArea !== snapshot.currentAreaId;
  return (
    <Link
      href={`/events/${event.eventId}`}
      className={styles.concernRow}
      data-priority={event.priority}
    >
      <span className={styles.concernIcon} aria-hidden="true">
        <AlertIcon />
      </span>
      <div className={styles.concernWho}>
        <span className={styles.priority} data-priority={event.priority}>
          {event.priority} priority
        </span>
        <span className={styles.concernResident}>
          {residentName(
            snapshot.profiles,
            event.resident.residentId,
            event.resident.displayLabel,
          )}
        </span>
        <span className={styles.concernRoom}>
          {" "}
          {event.resident.roomLabel}
          {outsideSelected ? " · other covered area" : ""}
        </span>
      </div>
      <div className={styles.concernCopy}>
        <h3>{event.headline}</h3>
        <p className={styles.meta}>
          Opened {careTime(event.createdAt, snapshot.facility.timeZone)}
          {event.overdue ? " · response overdue" : ""}
        </p>
      </div>
      <div className={styles.response}>
        <strong>{eventStateLabels[event.status]}</strong>
        {latest && (
          <span className={styles.meta}>
            {outcomeLabels[latest.outcome]}
            <br />
          </span>
        )}
        <span className={styles.meta}>{actor ?? "No response recorded"}</span>
      </div>
      <span className={styles.chevron} aria-hidden="true">
        <ArrowIcon />
      </span>
    </Link>
  );
}
export function FollowUpList({
  items,
  snapshot,
  editable = false,
}: {
  items: FollowUp[];
  snapshot: WorkspaceSnapshot;
  editable?: boolean;
}) {
  const permitted = hasWorkspacePermission(snapshot, "update_follow_up");
  return (
    <>
      <ul className={styles.plainList}>
        {items.map((item) => (
          <FollowUpItem
            key={item.followUpId}
            item={item}
            snapshot={snapshot}
            editable={editable && permitted}
          />
        ))}
      </ul>
      {editable &&
        !permitted &&
        items.some((item) => item.status !== "completed") && (
          <PermissionNotice action="update follow-up" />
        )}
    </>
  );
}
export function CompletedFollowUpHistory({
  items,
  snapshot,
}: {
  items: FollowUp[];
  snapshot: WorkspaceSnapshot;
}) {
  const completed = items
    .filter((item) => item.status === "completed")
    .sort(
      (a, b) =>
        Date.parse(b.completedAt ?? b.createdAt) -
        Date.parse(a.completedAt ?? a.createdAt),
    );
  if (!completed.length) return null;
  return (
    <details className={styles.completedFollowUps}>
      <summary>Completed follow-up history ({completed.length})</summary>
      <FollowUpList items={completed} snapshot={snapshot} />
    </details>
  );
}
function FollowUpItem({
  item,
  snapshot,
  editable,
}: {
  item: FollowUp;
  snapshot: WorkspaceSnapshot;
  editable: boolean;
}) {
  const { client, refresh } = useWorkspace();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [handoverNote, setHandoverNote] = useState("");
  const [showHandover, setShowHandover] = useState(false);
  async function save(kind: "complete" | "handover") {
    if (!hasWorkspacePermission(snapshot, "update_follow_up")) {
      setError(
        "This shared device is not permitted to update follow-up. Ask an administrator to review its permissions.",
      );
      return;
    }
    if (kind === "handover" && !handoverNote.trim()) {
      setError("Describe what the next team needs to do.");
      return;
    }
    setPending(true);
    setError("");
    setSaved("");
    try {
      if (kind === "complete") await client.completeFollowUp(item.followUpId);
      else await client.handOverFollowUp(item.followUpId, handoverNote);
      await refresh();
      setSaved(
        kind === "complete"
          ? "Follow-up marked complete in this demonstration."
          : "Handover recorded. The follow-up remains visible for the next team.",
      );
      setShowHandover(false);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "The change could not be confirmed. Your follow-up remains visible.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <li>
      <h3>{item.text}</h3>
      <p className={styles.meta}>
        <Link
          className={styles.textLink}
          href={`/residents/${item.residentId}`}
        >
          {residentName(snapshot.profiles, item.residentId, "Resident record")}
        </Link>{" "}
        ·{" "}
        {item.dueAt
          ? `Due ${careTime(item.dueAt, snapshot.facility.timeZone)}`
          : "No due time supplied"}
      </p>
      <p className={styles.meta}>
        {item.status === "handed_over"
          ? "Handed over · still outstanding"
          : item.status === "completed"
            ? "Completed"
            : "Open"}{" "}
        · {item.clientLabel}
      </p>
      {item.status === "completed" && (
        <p className={styles.meta}>
          Completed {careTime(item.completedAt, snapshot.facility.timeZone)}
        </p>
      )}
      {item.completionNote && <p>{item.completionNote}</p>}
      {item.history && item.history.length > 0 && (
        <details className={styles.followUpHistory}>
          <summary>
            Handover & completion history ({item.history.length})
          </summary>
          <ul className={styles.plainList}>
            {item.history.map((entry, index) => (
              <li key={`${entry.recordedAt}-${index}`}>
                <p>
                  {entry.action === "handed_over" ? "Handed over" : "Completed"}{" "}
                  · {careTime(entry.recordedAt, snapshot.facility.timeZone)}
                </p>
                {entry.note && <p>{entry.note}</p>}
                <p className={styles.meta}>{entry.clientLabel}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
      {item.eventId && (
        <Link className={styles.textLink} href={`/events/${item.eventId}`}>
          View concern
        </Link>
      )}
      {editable && item.status !== "completed" && (
        <div style={{ marginTop: 12 }}>
          <div className={styles.actionGroup}>
            <Button
              variant="secondary"
              pending={pending}
              onClick={() => void save("complete")}
            >
              Mark follow-up complete
            </Button>
            <Button
              variant="quiet"
              disabled={pending}
              onClick={() => setShowHandover(!showHandover)}
            >
              Hand over follow-up
            </Button>
          </div>
          {showHandover && (
            <div className={styles.form}>
              <FormField
                label="What remains for the next team"
                disabled={pending}
                as="textarea"
                value={handoverNote}
                onChange={(e) => setHandoverNote(e.target.value)}
              />
              <Button
                variant="secondary"
                pending={pending}
                onClick={() => void save("handover")}
              >
                Save handover
              </Button>
            </div>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className={styles.actionError}>
          {error}
        </p>
      )}
      {saved && (
        <p role="status" className={styles.saved}>
          {saved}
        </p>
      )}
    </li>
  );
}
