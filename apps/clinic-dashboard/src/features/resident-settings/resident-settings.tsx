"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ChevronLeftIcon } from "@/components/icons/icons";
import { StatusPill } from "@/components/status-pill/status-pill";
import {
  useMonitoringClient,
  type AwarenessDeliveryChoices,
  type NotificationDeliveryChoices,
  type ResidentDetailResponse,
  type ResidentMemoryEntry,
  type ResidentMemoryResponse,
  type ResidentNotificationPreferencesResponse,
} from "@/lib/monitoring";

import styles from "./resident-settings.module.css";

type SettingsData = {
  resident: ResidentDetailResponse;
  preferences: ResidentNotificationPreferencesResponse;
  memory: ResidentMemoryResponse;
};

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; data: SettingsData };

type EntryAction =
  | { mode: "correct"; entryId: string; description: string; reason: string }
  | { mode: "retire"; entryId: string; reason: string }
  | null;

const initialEventDelivery: NotificationDeliveryChoices = {
  watch: false,
  high: true,
  critical: true,
};

const initialAwarenessDelivery: AwarenessDeliveryChoices = {
  away: true,
  return: true,
  limited: false,
  unavailable: true,
};

const deliveryOptions: Array<{
  group: "event" | "awareness";
  key: keyof NotificationDeliveryChoices | keyof AwarenessDeliveryChoices;
  label: string;
  description: string;
}> = [
  { group: "event", key: "watch", label: "Watch events", description: "Lower-priority review items." },
  { group: "event", key: "high", label: "High-priority events", description: "Events that need timely staff attention." },
  { group: "event", key: "critical", label: "Critical events", description: "Events that need immediate staff attention." },
  { group: "awareness", key: "away", label: "Resident away", description: "When resident-specific monitoring pauses because the resident is away." },
  { group: "awareness", key: "return", label: "Resident returned", description: "When resident-specific monitoring can resume after an away period." },
  { group: "awareness", key: "limited", label: "Monitoring limited", description: "When room conditions reduce confidence." },
  { group: "awareness", key: "unavailable", label: "Monitoring unavailable", description: "When current resident monitoring cannot be provided." },
];

function formatTime(value: string | null): string {
  if (!value) return "Not saved yet";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function sourceLabel(entry: ResidentMemoryEntry): string {
  return entry.sourceKind === "feedback" ? "From event feedback" : "Staff added";
}

export function ResidentSettings({ residentId }: Readonly<{ residentId: string }>) {
  const client = useMonitoringClient();
  const [result, setResult] = useState<LoadState>({ status: "loading" });
  const [requestKey, setRequestKey] = useState(0);
  const [eventDelivery, setEventDelivery] = useState(initialEventDelivery);
  const [awarenessDelivery, setAwarenessDelivery] = useState(initialAwarenessDelivery);
  const [newContext, setNewContext] = useState("");
  const [entryAction, setEntryAction] = useState<EntryAction>(null);
  const [saving, setSaving] = useState<"preferences" | "memory" | null>(null);
  const [memoryMessage, setMemoryMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [preferenceMessage, setPreferenceMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    let current = true;
    Promise.all([
        client.getResident(residentId),
        client.getNotificationPreferences(residentId),
        client.getResidentMemory(residentId),
      ])
      .then(([resident, preferences, memory]) => {
        if (!current) return;
      setEventDelivery(preferences.eventDelivery ?? initialEventDelivery);
      setAwarenessDelivery(preferences.awarenessDelivery ?? initialAwarenessDelivery);
      setResult({ status: "success", data: { resident, preferences, memory } });
      })
      .catch(() => { if (current) setResult({ status: "error" }); });
    return () => { current = false; };
  }, [client, residentId, requestKey]);

  const orderedEntries = useMemo(() => {
    if (result.status !== "success") return [];
    return [...result.data.memory.entries].sort((left, right) => {
      if (left.status !== right.status) return left.status === "active" ? -1 : 1;
      return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime();
    });
  }, [result]);

  function updateMemory(memory: ResidentMemoryResponse, message: string) {
    if (result.status !== "success") return;
    setResult({ status: "success", data: { ...result.data, memory } });
    setMemoryMessage({ tone: "success", text: message });
    setEntryAction(null);
  }

  async function addContext(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (result.status !== "success") return;
    setSaving("memory");
    setMemoryMessage(null);
    try {
      const memory = await client.addMemoryEntry(residentId, { expectedVersion: result.data.memory.version, description: newContext });
      setNewContext("");
      updateMemory(memory, "Resident context saved. Calibration and warning rules were not changed.");
    } catch (error) {
      setMemoryMessage({ tone: "error", text: error instanceof Error ? error.message : "Resident context could not be saved." });
    } finally {
      setSaving(null);
    }
  }

  async function submitEntryAction(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (result.status !== "success" || !entryAction) return;
    setSaving("memory");
    setMemoryMessage(null);
    try {
      const memory = entryAction.mode === "correct"
        ? await client.correctMemoryEntry(residentId, entryAction.entryId, { expectedVersion: result.data.memory.version, description: entryAction.description, reason: entryAction.reason })
        : await client.retireMemoryEntry(residentId, entryAction.entryId, { expectedVersion: result.data.memory.version, reason: entryAction.reason });
      updateMemory(memory, entryAction.mode === "correct" ? "Correction saved. The original context remains in history." : "Context retired. Its history remains available.");
    } catch (error) {
      setMemoryMessage({ tone: "error", text: error instanceof Error ? error.message : "The context change could not be saved." });
    } finally {
      setSaving(null);
    }
  }

  async function savePreferences(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (result.status !== "success") return;
    setSaving("preferences");
    setPreferenceMessage(null);
    try {
      const preferences = await client.updateNotificationPreferences(residentId, {
        expectedVersion: result.data.preferences.version ?? 0,
        eventDelivery,
        awarenessDelivery,
      });
      setResult({ status: "success", data: { ...result.data, preferences } });
      setPreferenceMessage({ tone: "success", text: "Future delivery preferences saved." });
    } catch (error) {
      setPreferenceMessage({ tone: "error", text: error instanceof Error ? error.message : "Preferences could not be saved." });
    } finally {
      setSaving(null);
    }
  }

  if (result.status === "loading") return <div className={styles.message} role="status">Opening resident settings…</div>;
  if (result.status === "error") return <div className={styles.message} role="alert"><h1>Resident settings are unavailable</h1><p>No context or delivery choice has been changed.</p><button type="button" onClick={() => { setResult({ status: "loading" }); setRequestKey((value) => value + 1); }}>Try again</button><Link href={`/residents/${residentId}`}>Return to resident</Link></div>;

  const { resident, preferences, memory } = result.data;
  const activeCount = memory.entries.filter((entry) => entry.status === "active").length;

  return (
    <section className={styles.page}>
      <Link className={styles.back} href={`/residents/${residentId}`}><ChevronLeftIcon />{resident.resident.displayLabel}</Link>
      <header className={styles.header}><div><h1>Context &amp; notifications</h1><span>{resident.resident.displayLabel} · {resident.resident.roomLabel}</span></div><StatusPill label={`${activeCount} active context ${activeCount === 1 ? "item" : "items"}`} tone={activeCount ? "healthy" : "neutral"} /></header>

      <div className={styles.boundaryNote}>
        <div><strong>Context helps explain events</strong><p>These notes describe routines. They do not directly change the numerical calibration or safety rules.</p></div>
        <div><strong>Preferences control future delivery</strong><p>High and critical events always stay visible in the clinic dashboard.</p></div>
      </div>

      <div className={styles.layout}>
        <div className={styles.mainColumn}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><div><h2>Resident context</h2><p>A versioned record of routines and useful background for future event explanations.</p></div><span>Memory version {memory.version}</span></div>
            <form className={styles.addForm} onSubmit={(event) => void addContext(event)}>
              <label htmlFor="new-context">Add useful context</label>
              <textarea id="new-context" value={newContext} maxLength={240} placeholder="Example: Assisted walking is common after lunch." onChange={(event) => setNewContext(event.target.value)} />
              <div><small>{newContext.length}/240</small><button type="submit" disabled={saving === "memory"}>{saving === "memory" ? "Saving…" : "Add context"}</button></div>
            </form>
            {memoryMessage && <p className={styles.feedback} data-tone={memoryMessage.tone} role={memoryMessage.tone === "error" ? "alert" : "status"}>{memoryMessage.text}</p>}
            <div className={styles.entryList}>
              {orderedEntries.length === 0 ? <div className={styles.empty}><strong>No resident context has been saved</strong><p>Add only information that helps staff understand a normal routine or future event.</p></div> : orderedEntries.map((entry) => (
                <article className={styles.entry} data-status={entry.status} key={entry.entryId}>
                  <div className={styles.entryTop}><div><span>{sourceLabel(entry)}</span><StatusPill label={entry.status} tone={entry.status === "active" ? "healthy" : "neutral"} /></div><time dateTime={entry.createdAt}>{formatTime(entry.createdAt)}</time></div>
                  <p className={styles.entryDescription}>{entry.description}</p>
                  <div className={styles.entryMeta}><span>Recorded by {entry.createdBy}</span>{entry.supersedesEntryId && <span>Corrects an earlier entry</span>}{entry.retirementReason && <span>Retired because: {entry.retirementReason}</span>}</div>
                  {entry.status === "active" && <div className={styles.entryActions}><button type="button" onClick={() => setEntryAction({ mode: "correct", entryId: entry.entryId, description: entry.description, reason: "" })}>Correct</button><button type="button" onClick={() => setEntryAction({ mode: "retire", entryId: entry.entryId, reason: "" })}>Retire</button></div>}
                  {entryAction?.entryId === entry.entryId && <form className={styles.actionForm} onSubmit={(event) => void submitEntryAction(event)}>
                    {entryAction.mode === "correct" && <label>Corrected context<textarea value={entryAction.description} maxLength={240} onChange={(event) => setEntryAction({ ...entryAction, description: event.target.value })} /></label>}
                    <label>Reason for {entryAction.mode === "correct" ? "correction" : "retirement"}<input value={entryAction.reason} maxLength={160} placeholder={entryAction.mode === "correct" ? "Example: The time was entered incorrectly." : "Example: This routine is no longer current."} onChange={(event) => setEntryAction({ ...entryAction, reason: event.target.value })} /></label>
                    <div><button type="button" onClick={() => setEntryAction(null)}>Cancel</button><button type="submit" disabled={saving === "memory"}>{saving === "memory" ? "Saving…" : entryAction.mode === "correct" ? "Save correction" : "Retire context"}</button></div>
                  </form>}
                </article>
              ))}
            </div>
          </section>
        </div>

        <aside className={styles.sidebar}>
          <form className={styles.preferencePanel} onSubmit={(event) => void savePreferences(event)}>
            <div className={styles.preferenceHeader}><div><h2>Notification delivery</h2><p>Choose which future updates are delivered outside this dashboard.</p></div><span>{preferences.version ? `Version ${preferences.version}` : "Not saved"}</span></div>
            {preferences.dataAvailability === "not_yet_available" && <div className={styles.firstSave}><strong>No choices have been saved yet</strong><p>The form starts with clearly labeled demo choices. Review every switch before the first save.</p></div>}
            <fieldset><legend>Event delivery</legend>{deliveryOptions.filter((option) => option.group === "event").map((option) => { const key = option.key as keyof NotificationDeliveryChoices; return <label className={styles.switchRow} key={option.label}><span><strong>{option.label}</strong><small>{option.description}</small></span><input type="checkbox" checked={eventDelivery[key]} onChange={() => setEventDelivery((current) => ({ ...current, [key]: !current[key] }))} /></label>; })}</fieldset>
            <div className={styles.alwaysVisible}><strong>Dashboard safety rule</strong><p>High and critical events remain visible here even when delivery is turned off.</p></div>
            <fieldset><legend>Awareness delivery</legend>{deliveryOptions.filter((option) => option.group === "awareness").map((option) => { const key = option.key as keyof AwarenessDeliveryChoices; return <label className={styles.switchRow} key={option.label}><span><strong>{option.label}</strong><small>{option.description}</small></span><input type="checkbox" checked={awarenessDelivery[key]} onChange={() => setAwarenessDelivery((current) => ({ ...current, [key]: !current[key] }))} /></label>; })}</fieldset>
            {preferenceMessage && <p className={styles.feedback} data-tone={preferenceMessage.tone} role={preferenceMessage.tone === "error" ? "alert" : "status"}>{preferenceMessage.text}</p>}
            <button className={styles.saveButton} type="submit" disabled={saving === "preferences"}>{saving === "preferences" ? "Saving preferences…" : "Save delivery preferences"}</button>
            <p className={styles.changedAt}>Last saved {formatTime(preferences.changedAt)}{preferences.changedBy ? ` by ${preferences.changedBy}` : ""}</p>
          </form>
        </aside>
      </div>
    </section>
  );
}
