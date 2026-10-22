"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useWorkspace } from "@/lib/workspace";
import { eventStateLabels, residentName } from "./care-format";
import { EventActions, type ResponseMode } from "./care-response-actions";
import { HistoricalPriority, ResolvedConcernStatus } from "./care-shared";
import styles from "./care-workspace.module.css";

export function useConcernResponseDialog() {
  const [selection, setSelection] = useState<{ eventId: string; mode: ResponseMode } | null>(null);
  return {
    openResponse: (eventId: string, mode: ResponseMode = "response") => setSelection({ eventId, mode }),
    responseDialog: selection ? (
      <ConcernResponseDialog key={selection.eventId} eventId={selection.eventId} initialMode={selection.mode} onClose={() => setSelection(null)} />
    ) : null,
  };
}

function ConcernResponseDialog({ eventId, initialMode, onClose }: {
  eventId: string;
  initialMode: ResponseMode;
  onClose: () => void;
}) {
  const { snapshot, status } = useWorkspace();
  const [pending, setPending] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const discardHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (confirmDiscard) discardHeading.current?.focus();
  }, [confirmDiscard]);
  // Always use the latest authorized record, including changes made while this is open.
  const event = status !== "error" ? snapshot?.events.find((item) => item.eventId === eventId) : undefined;
  const resolved = event?.status === "resolved";
  function requestClose() {
    if (pending && event && !resolved) return;
    if (dirty && event && !resolved) setConfirmDiscard(true);
    else onClose();
  }
  function requestDiscard() {
    if (!pending) onClose();
  }
  return (
    <Modal open title="Response & outcome" closeLabel="Close response" onRequestClose={requestClose} dismissDisabled={pending && Boolean(event) && !resolved}>
      {event && snapshot ? (
        <>
          <div className={styles.responseContext}>
            <p className={styles.eventResident}>{event.resident.roomLabel} <span>·</span> {residentName(snapshot.profiles, event.resident.residentId, event.resident.displayLabel)}</p>
            <h3>{event.headline}</h3>
            <div className={styles.eventMetadata}>
              {resolved ? <HistoricalPriority priority={event.priority} /> : <><span className={styles.priority} data-priority={event.priority}>{event.priority} priority</span><span className={styles.responseState}>{eventStateLabels[event.status]}</span></>}
            </div>
            {event.confidence.limitation && <p className={styles.finePrint}>{event.confidence.limitation}</p>}
          </div>
          {resolved ? (
            <section className={styles.resolved} aria-label="Resolution saved" role="status">
              <ResolvedConcernStatus />
              <p>{event.feedback?.actualEventLabel ?? "The concern has been explicitly resolved. Its history is preserved."}</p>
              <p className={styles.finePrint}>This completes the concern record. It does not confirm resident health or monitoring coverage.</p>
            </section>
          ) : (
            <>
              {confirmDiscard && <section className={styles.discardPrompt} aria-label="Unsaved response" role="alert">
                <h3 ref={discardHeading} tabIndex={-1}>Discard this unsaved entry?</h3>
                <p>Your changes have not been saved.</p>
                <div className={styles.inlineActions}>
                  <Button disabled={pending} onClick={() => setConfirmDiscard(false)}>Keep editing</Button>
                  <Button variant="secondary" disabled={pending} onClick={requestDiscard}>Discard and close</Button>
                </div>
              </section>}
              <div hidden={confirmDiscard}><EventActions event={event} snapshot={snapshot} initialMode={initialMode} onPendingChange={setPending} onDirtyChange={setDirty} /></div>
            </>
          )}
        </>
      ) : <p role="status">This concern is no longer available in this device’s current access. Close this window to review the current workspace.</p>}
    </Modal>
  );
}
