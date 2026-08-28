"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";
import { ArrowIcon, CheckIcon, InfoIcon } from "@/components/icons";
import { useHomeMonitoringClient, type HomeFeedbackSummary, type HomeUpdateDetail } from "@/lib/home-monitoring";
import styles from "./update-detail.module.css";

const outcomeLabels: Record<HomeFeedbackSummary["outcome"], string> = {
  expected: "This was expected",
  not_expected: "This was not expected",
  unsure: "I’m not sure",
};

function timeLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", { weekday: "long", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

export function UpdateDetail({ eventId }: { eventId: string }) {
  const client = useHomeMonitoringClient();
  const [update, setUpdate] = useState<HomeUpdateDetail | null>();
  const [failed, setFailed] = useState(false);
  const [outcome, setOutcome] = useState<HomeFeedbackSummary["outcome"] | "">("");
  const [note, setNote] = useState("");
  const [remember, setRemember] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    let active = true;
    client.getUpdate(eventId).then((response) => { if (active) setUpdate(response); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [client, eventId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!outcome) { setFormError("Choose the answer that fits best."); return; }
    setSaving(true); setFormError("");
    try { setUpdate(await client.saveUpdateFeedback(eventId, { outcome, note, shouldRememberRoutine: remember })); }
    catch (error) { setFormError(error instanceof Error ? error.message : "The explanation could not be saved."); }
    finally { setSaving(false); }
  }

  if (failed) return <PageState role="alert" title="This update could not load" detail="The demo information is temporarily unavailable. Nothing has been guessed." />;
  if (update === undefined) return <PageState role="status" title="Opening the update" detail="Gathering the plain-language explanation." loading />;
  if (update === null) return <PageState title="This update could not be found" detail="It may no longer be available in this demo." />;

  return <div className={styles.page}>
    <Link href="/" className={styles.backLink}><ArrowIcon/> Back to today</Link>
    <header className={styles.hero}>
      <div className={styles.heroMeta}><span>Important update</span><time dateTime={update.occurredAt}>{timeLabel(update.occurredAt)}</time></div>
      <h1>{update.headline}</h1>
      <p>{update.summary}</p>
    </header>

    <div className={styles.contentGrid}>
      <div className={styles.story}>
        <section className={styles.sheet} aria-labelledby="changed-heading">
          <p className={styles.eyebrow}>What changed</p><h2 id="changed-heading">A brief change from the usual routine</h2><p className={styles.lead}>{update.whatChanged}</p>
          <div className={styles.observations}>
            <h3>What was noticed</h3>
            <ul>{update.observations.map((item) => <li key={item}><CheckIcon/><span>{item}</span></li>)}</ul>
          </div>
        </section>

        <section className={styles.unknown} aria-labelledby="unknown-heading"><InfoIcon/><div><p className={styles.eyebrow}>What remains unknown</p><h2 id="unknown-heading">The cause is not confirmed</h2><p>{update.limitation}</p><p>{update.interpretation}</p></div></section>
        <section className={styles.nextStep}><p className={styles.eyebrow}>A reasonable next step</p><h2>Use what you know about their day</h2><p>{update.checkInSuggestion}</p></section>
      </div>

      <aside className={styles.feedbackCard} aria-labelledby="feedback-heading">
        {update.feedback ? <SavedFeedback feedback={update.feedback} /> : <form onSubmit={submit}>
          <p className={styles.eyebrow}>Add family context</p><h2 id="feedback-heading">Did this fit their routine?</h2><p className={styles.formIntro}>Your answer helps future updates make more sense. It does not erase what happened.</p>
          <fieldset><legend>Choose one answer</legend>
            {(["expected", "not_expected", "unsure"] as const).map((value) => <label className={styles.radioChoice} key={value}><input type="radio" name="outcome" value={value} checked={outcome === value} onChange={() => setOutcome(value)}/><span><strong>{outcomeLabels[value]}</strong><small>{value === "expected" ? "This matched something you know about." : value === "not_expected" ? "This did not match their normal day." : "You do not have enough context yet."}</small></span></label>)}
          </fieldset>
          <label className={styles.noteLabel} htmlFor="family-note">Anything else we should know? <span>Optional</span></label>
          <textarea id="family-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={240} placeholder="For example: They started a new evening stretch." />
          <div className={styles.characterCount}>{note.length}/240</div>
          <label className={styles.checkChoice}><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)}/><span>Remember this as part of their usual routine</span></label>
          {formError && <p className={styles.formError} role="alert">{formError}</p>}
          <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save explanation"}</button>
          <p className={styles.privacyNote}>This synthetic demo stores the answer only in this browser.</p>
        </form>}
      </aside>
    </div>
  </div>;
}

function SavedFeedback({ feedback }: { feedback: HomeFeedbackSummary }) {
  return <div className={styles.saved}>
    <span className={styles.savedIcon}><CheckIcon/></span>
    <p className={styles.eyebrow}>Explanation saved</p>
    <h2 id="feedback-heading">Thank you for adding context.</h2>
    <dl><div><dt>Your answer</dt><dd>{outcomeLabels[feedback.outcome]}</dd></div>{feedback.note && <div><dt>Your note</dt><dd>{feedback.note}</dd></div>}<div><dt>Routine memory</dt><dd>{feedback.shouldRememberRoutine ? "Save as useful routine context" : "Do not add to routine context"}</dd></div></dl>
    <p className={styles.savedNote}>The original update stays unchanged. Your explanation is kept beside it.</p>
    <Link href="/">Return to today <ArrowIcon/></Link>
  </div>;
}

function PageState({ title, detail, role, loading = false }: { title: string; detail: string; role?: "alert" | "status"; loading?: boolean }) {
  return <section className={styles.pageState} role={role}>{loading ? <span className={styles.loadingDot}/> : <span className={styles.stateIcon}><InfoIcon/></span>}<h1>{title}</h1><p>{detail}</p><Link href="/">Return to today</Link></section>;
}
