"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { FacilityTimeField } from "@/components/ui/facility-time-field";
import {
  useWorkspace,
  type ContextRecord,
  type ResidentProfile,
  type WorkspaceSnapshot,
} from "@/lib/workspace";
import { careTime } from "@/features/workspace/care-format";
import {
  AdminFrame,
  errorMessage,
  SaveMessage,
  SectionHeading,
} from "./admin-common";
import styles from "./workspace-admin.module.css";

const categoryLabels: Record<ContextRecord["category"], string> = {
  preference: "Resident preference",
  care_goal: "Care or comfort goal",
  hospice: "Hospice context",
  observation: "Staff observation",
  correction: "Correction report",
};

function ContextHistory({
  records,
  snapshot,
}: {
  records: ContextRecord[];
  snapshot: WorkspaceSnapshot;
}) {
  if (!records.length)
    return (
      <p className={styles.notice}>
        No context records were supplied for this resident. Care goals, usual
        routines and service contacts remain unknown.
      </p>
    );
  return (
    <ol className={styles.contextHistory}>
      {[...records].reverse().map((record) => {
        const expired =
          record.effectiveUntil !== null &&
          Date.parse(record.effectiveUntil) <=
            Date.parse(snapshot.synchronizedAt);
        const prior = records.find(
          (item) => item.contextId === record.supersedesContextId,
        );
        return (
          <li key={record.contextId} id={`context-${record.contextId}`}>
            <div className={styles.recordHeading}>
              <h3>{categoryLabels[record.category]}</h3>
              <span className={styles.reviewState}>
                {record.reviewStatus === "needs_review"
                  ? "Needs review"
                  : "Reviewed in demonstration"}
              </span>
            </div>
            <p className={styles.contextText}>{record.text}</p>
            <dl className={styles.contextProvenance}>
              <div>
                <dt>Source</dt>
                <dd>{record.source}</dd>
              </div>
              <div>
                <dt>Recorded</dt>
                <dd>
                  <time dateTime={record.recordedAt}>
                    {careTime(record.recordedAt, snapshot.facility.timeZone)}
                  </time>
                </dd>
              </div>
              {record.effectiveUntil ? (
                <div>
                  <dt>{expired ? "Expired" : "Effective until"}</dt>
                  <dd>
                    <time dateTime={record.effectiveUntil}>
                      {careTime(
                        record.effectiveUntil,
                        snapshot.facility.timeZone,
                      )}
                    </time>
                    {expired ? " · historical context" : ""}
                  </dd>
                </div>
              ) : (
                <div>
                  <dt>Expiration</dt>
                  <dd>Not supplied</dd>
                </div>
              )}
              {record.supersedesContextId ? (
                <div>
                  <dt>Correction to</dt>
                  <dd>
                    {prior ? (
                      <a href={`#context-${prior.contextId}`}>
                        {categoryLabels[prior.category]} ·{" "}
                        {careTime(prior.recordedAt, snapshot.facility.timeZone)}
                      </a>
                    ) : (
                      "Source record was not supplied in this view"
                    )}
                  </dd>
                </div>
              ) : null}
            </dl>
            {record.reviewStatus === "needs_review" ? (
              <p className={styles.muted}>
                Reported information awaiting review. Earlier source records and
                approved instructions have not been replaced.
              </p>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function ContextForm({
  profile,
  records,
  timeZone,
}: {
  profile: ResidentProfile;
  records: ContextRecord[];
  timeZone: string;
}) {
  const { client, refresh } = useWorkspace();
  const [category, setCategory] =
    useState<ContextRecord["category"]>("observation");
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [sourceDate, setSourceDate] = useState("");
  const [effectiveUntil, setEffectiveUntil] = useState("");
  const [target, setTarget] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    if (!text.trim() || !source.trim()) {
      setError(
        "Add the context detail and its source before saving for review.",
      );
      return;
    }
    if (category === "correction" && !target) {
      setError("Choose the source record this correction refers to.");
      return;
    }
    if (
      sourceDate &&
      (!/^\d{4}-\d{2}-\d{2}$/.test(sourceDate) ||
        !Number.isFinite(Date.parse(`${sourceDate}T00:00:00Z`)) ||
        new Date(`${sourceDate}T00:00:00Z`).toISOString().slice(0, 10) !==
          sourceDate)
    ) {
      setError("Enter a valid source calendar date.");
      return;
    }
    setPending(true);
    try {
      await client.addContext(profile.residentId, {
        category,
        text: text.trim(),
        source: sourceDate
          ? `${source.trim()} · source date ${sourceDate}`
          : source.trim(),
        effectiveUntil: effectiveUntil.trim() || null,
        ...(category === "correction" ? { supersedesContextId: target } : {}),
      });
      await refresh();
      setText("");
      setSource("");
      setSourceDate("");
      setEffectiveUntil("");
      setTarget("");
      setMessage(
        "Context saved in this demo. Review is still needed; no clinical plan or notification policy was changed.",
      );
    } catch (cause) {
      const detail = errorMessage(cause);
      setError(
        /ISO date|calendar|time zone/i.test(detail)
          ? "Choose a valid facility date and time for expiration, including which occurrence if the time happens twice. Your context was not saved."
          : detail,
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={save} className={styles.form}>
      <FormField
        as="select"
        label="Context category"
        value={category}
        disabled={pending}
        onChange={(event) => {
          setCategory(event.target.value as ContextRecord["category"]);
          setMessage("");
        }}
        options={Object.entries(categoryLabels).map(([value, label]) => ({
          value,
          label,
          disabled: value === "correction" && !records.length,
        }))}
      />
      {category === "correction" ? (
        <FormField
          as="select"
          label="Record to correct"
          value={target}
          disabled={pending}
          required
          onChange={(event) => setTarget(event.target.value)}
          options={[
            { value: "", label: "Choose an earlier source record" },
            ...records.map((record) => ({
              value: record.contextId,
              label: `${categoryLabels[record.category]} · ${record.text.slice(0, 90)}`,
            })),
          ]}
        />
      ) : null}
      <FormField
        as="textarea"
        label="Context detail"
        required
        rows={4}
        maxLength={2400}
        value={text}
        disabled={pending}
        onChange={(event) => setText(event.target.value)}
        hint="Use synthetic information. Record a preference, observation or sourced instruction without turning it into a new treatment order."
      />
      <div className={styles.fieldGrid}>
        <FormField
          label="Source description"
          required
          value={source}
          maxLength={400}
          disabled={pending}
          onChange={(event) => setSource(event.target.value)}
          placeholder="For example, synthetic resident interview"
        />
        <FormField
          label="Source date (optional)"
          type="date"
          value={sourceDate}
          disabled={pending}
          onChange={(event) => setSourceDate(event.target.value)}
          hint="Stored with the source description. It does not change the time this report is saved."
        />
        <FacilityTimeField
          label="Context expires (optional)"
          value={effectiveUntil}
          disabled={pending}
          timeZone={timeZone}
          onChange={setEffectiveUntil}
          hint="Leave empty if no expiration was supplied."
        />
      </div>
      <p className={styles.muted}>
        The save time is recorded automatically. Every new entry needs review,
        including entries submitted from demo administration. Corrections append
        a report and preserve the original. The service has no clinical approval
        action.
      </p>
      <div className={styles.formFooter}>
        <Button type="submit" pending={pending} pendingLabel="Saving context…">
          Save context for review
        </Button>
        <SaveMessage message={message} error={error} />
      </div>
    </form>
  );
}

export function ResidentAdministration({ residentId }: { residentId: string }) {
  const { snapshot } = useWorkspace();
  const profile = snapshot?.profiles.find(
    (item) => item.residentId === residentId,
  );
  const records =
    snapshot?.contexts.filter((item) => item.residentId === residentId) ?? [];
  return (
    <AdminFrame
      title="Resident administration"
      description="Maintain sourced context without overwriting earlier reports or changing clinical policy."
    >
      {snapshot && !profile ? (
        <section className={styles.section} role="alert">
          <h2>Resident administration is unavailable</h2>
          <p className={styles.intro}>
            The resident is outside this station’s approved coverage or the
            record is unavailable. Administrative mode does not expand routine
            resident scope.
          </p>
          <Link className={styles.inlineLink} href="/residents">
            Return to the authorized directory →
          </Link>
        </section>
      ) : null}
      {snapshot && profile ? (
        <>
          <section className={styles.section}>
            <SectionHeading
              number="01"
              title={profile.name}
              description={`${profile.roomLabel} · ${snapshot.areas.find((area) => area.areaId === profile.areaId)?.name ?? "Area unavailable"}`}
            />
            <dl className={styles.details}>
              <div>
                <dt>Resident record</dt>
                <dd>{profile.facilityResidentId}</dd>
              </div>
              <div>
                <dt>Assignment effective</dt>
                <dd>
                  {careTime(
                    profile.assignmentEffectiveAt,
                    snapshot.facility.timeZone,
                  )}
                </dd>
              </div>
              {profile.departedAt ? (
                <div>
                  <dt>Departure recorded</dt>
                  <dd>
                    {careTime(profile.departedAt, snapshot.facility.timeZone)} ·
                    historical resident record
                  </dd>
                </div>
              ) : null}
              <div>
                <dt>Time zone</dt>
                <dd>{snapshot.facility.timeZone}</dd>
              </div>
            </dl>
            <Link
              className={styles.inlineLink}
              href={`/residents/${residentId}`}
            >
              Open care record →
            </Link>
          </section>
          <section className={styles.section}>
            <SectionHeading
              number="02"
              title="Context and provenance"
              description="Source statements, review state and effective dates remain visible. A staff report is distinct from approved clinical instructions."
            />
            <ContextHistory records={records} snapshot={snapshot} />
          </section>
          <section className={styles.section}>
            <SectionHeading
              number="03"
              title="Add sourced context"
              description="Enter new information or append a correction for review. Use the authorized clinical process to confirm any care instruction."
            />
            <ContextForm
              key={profile.residentId}
              profile={profile}
              records={records}
              timeZone={snapshot.facility.timeZone}
            />
          </section>
          <section className={styles.section}>
            <SectionHeading number="04" title="Notification policy" />
            <div className={styles.readiness}>
              <span className={styles.readinessMark} aria-hidden="true">
                !
              </span>
              <div>
                <h3>Notification policy is not connected</h3>
                <p>
                  Resident-specific delivery preferences and clinical routing
                  approval are not available from this service. Saving context
                  does not change alert destinations or prove that any
                  notification was delivered.
                </p>
              </div>
            </div>
            <p className={styles.muted}>
              Hospice status, comfort goals or a DNR statement do not by
              themselves stop notifications. Follow the resident’s authorized
              care plan and facility procedure.
            </p>
            <div className={styles.relatedLinks}>
              <Link href="/notifications">Review notification readiness ↗</Link>
              <Link href="/station">Review station coverage ↗</Link>
            </div>
          </section>
        </>
      ) : null}
    </AdminFrame>
  );
}
