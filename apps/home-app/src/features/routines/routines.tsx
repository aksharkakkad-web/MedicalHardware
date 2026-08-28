"use client";

import { type FormEvent, useEffect, useState } from "react";
import { CheckIcon, InfoIcon, RoutineIcon } from "@/components/icons";
import { useHomeMonitoringClient, type HomeRoutineEntry, type HomeRoutinesResponse } from "@/lib/home-monitoring";
import styles from "./routines.module.css";

function dateLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function Routines() {
  const client = useHomeMonitoringClient();
  const [routines, setRoutines] = useState<HomeRoutinesResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [description, setDescription] = useState("");
  const [retiringId, setRetiringId] = useState<string | null>(null);
  const [retireReason, setRetireReason] = useState("");
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    let active = true;
    client.getRoutines().then((response) => { if (active) setRoutines(response); }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [client]);

  async function addRoutine(event: FormEvent) {
    event.preventDefault();
    if (!routines) return;
    setWorking(true); setFormError(""); setMessage("");
    try {
      setRoutines(await client.addRoutine({ expectedVersion: routines.version, description }));
      setDescription(""); setMessage("Routine added. It can now help explain future changes.");
    } catch (error) { setFormError(error instanceof Error ? error.message : "The routine could not be added."); }
    finally { setWorking(false); }
  }

  async function retireRoutine(event: FormEvent, routineId: string) {
    event.preventDefault();
    if (!routines) return;
    setWorking(true); setFormError(""); setMessage("");
    try {
      setRoutines(await client.retireRoutine(routineId, { expectedVersion: routines.version, reason: retireReason }));
      setRetiringId(null); setRetireReason(""); setMessage("Routine moved to past routines. Its history was kept.");
    } catch (error) { setFormError(error instanceof Error ? error.message : "The routine could not be updated."); }
    finally { setWorking(false); }
  }

  if (failed) return <PageState role="alert" title="Routines could not load" detail="The demo information is temporarily unavailable. No routine information has been guessed." />;
  if (!routines) return <PageState role="status" title="Opening routines" detail="Gathering the household context saved in this demo." loading />;

  const active = routines.entries.filter((entry) => entry.status === "active");
  const retired = routines.entries.filter((entry) => entry.status === "retired");

  return <div className={styles.page}>
    <header className={styles.hero}>
      <p className={styles.eyebrow}>Household context</p>
      <h1>Keep everyday context current.</h1>
      <p>Simple routines help the system understand what is normal for this home—without pretending every day will be identical.</p>
    </header>

    <section className={styles.explainer}><InfoIcon/><div><strong>Why this helps</strong><p>“Usually reads after dinner” is more useful than a technical number. Routines add context; they never block an important update.</p></div></section>

    <div className={styles.contentGrid}>
      <section aria-labelledby="current-heading">
        <div className={styles.sectionHeading}><div><p className={styles.eyebrow}>Current routines</p><h2 id="current-heading">What usually happens</h2></div><span>{active.length} active</span></div>
        <div className={styles.routineList}>
          {active.length ? active.map((routine) => <ActiveRoutine key={routine.routineId} routine={routine} retiring={retiringId === routine.routineId} reason={retireReason} error={retiringId === routine.routineId ? formError : ""} working={working} onBegin={() => { setRetiringId(routine.routineId); setRetireReason(""); setFormError(""); }} onCancel={() => { setRetiringId(null); setRetireReason(""); setFormError(""); }} onReason={setRetireReason} onSubmit={(event) => void retireRoutine(event, routine.routineId)} />) : <div className={styles.empty}><RoutineIcon/><p>No current routines have been added yet.</p></div>}
        </div>

        {retired.length > 0 && <details className={styles.history}>
          <summary><span>Past routines</span><small>{retired.length} kept for history</small></summary>
          <div>{retired.map((routine) => <article key={routine.routineId}><p>{routine.description}</p><span>Ended {routine.retiredAt ? dateLabel(routine.retiredAt) : "previously"}</span>{routine.retirementReason && <small>{routine.retirementReason}</small>}</article>)}</div>
        </details>}
      </section>

      <aside className={styles.addCard} aria-labelledby="add-heading">
        <span className={styles.addIcon}><RoutineIcon/></span>
        <p className={styles.eyebrow}>Add context</p><h2 id="add-heading">Describe one routine</h2>
        <p className={styles.addIntro}>Write one short sentence about something that commonly happens.</p>
        <form onSubmit={addRoutine}>
          <label htmlFor="routine-description">Describe one routine</label>
          <textarea id="routine-description" value={description} onChange={(event) => setDescription(event.target.value)} maxLength={160} placeholder="Usually takes a short walk after lunch" />
          <div className={styles.characterCount}>{description.length}/160</div>
          {formError && !retiringId && <p className={styles.formError} role="alert">{formError}</p>}
          <button type="submit" disabled={working}>{working && !retiringId ? "Adding…" : "Add routine"}</button>
        </form>
        <p className={styles.storageNote}>In this synthetic demo, routines are saved only in this browser.</p>
      </aside>
    </div>
    {message && <div className={styles.toast} role="status"><CheckIcon/><span>{message}</span></div>}
  </div>;
}

function ActiveRoutine({ routine, retiring, reason, error, working, onBegin, onCancel, onReason, onSubmit }: { routine: HomeRoutineEntry; retiring: boolean; reason: string; error: string; working: boolean; onBegin(): void; onCancel(): void; onReason(value: string): void; onSubmit(event: FormEvent): void }) {
  return <article className={styles.routineCard}>
    <div className={styles.routineIcon}><RoutineIcon/></div>
    <div className={styles.routineBody}><p>{routine.description}</p><span>Added {dateLabel(routine.createdAt)}</span>
      {retiring ? <form className={styles.retireForm} onSubmit={onSubmit}>
        <label htmlFor={`retire-${routine.routineId}`}>Why is this no longer current?</label>
        <input id={`retire-${routine.routineId}`} value={reason} onChange={(event) => onReason(event.target.value)} maxLength={120} placeholder="For example: Their schedule changed" autoFocus />
        {error && <p className={styles.formError} role="alert">{error}</p>}
        <div><button type="button" onClick={onCancel}>Cancel</button><button type="submit" disabled={working}>{working ? "Moving…" : "Move to past routines"}</button></div>
      </form> : <button className={styles.retireButton} type="button" onClick={onBegin}>No longer current</button>}
    </div>
  </article>;
}

function PageState({ title, detail, role, loading = false }: { title: string; detail: string; role: "alert" | "status"; loading?: boolean }) {
  return <section className={styles.pageState} role={role}>{loading ? <span className={styles.loadingDot}/> : <span className={styles.stateIcon}><InfoIcon/></span>}<h1>{title}</h1><p>{detail}</p></section>;
}
