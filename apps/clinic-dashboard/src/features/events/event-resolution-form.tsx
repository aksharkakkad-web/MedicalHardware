"use client";

import { useState } from "react";

import type { EventFeedbackInput, ResolutionOutcome } from "@/lib/monitoring";

import styles from "./event-detail.module.css";

const outcomes: Array<{
  value: ResolutionOutcome;
  label: string;
  description: string;
}> = [
  {
    value: "confirmed",
    label: "Confirmed event",
    description: "The event reflected a real situation that needed attention.",
  },
  {
    value: "false_positive",
    label: "False alarm",
    description: "Nothing concerning happened or the event was caused by normal activity.",
  },
  {
    value: "uncertain",
    label: "Unsure",
    description: "There is not enough information to confidently classify the event.",
  },
];

export function EventResolutionForm({
  isSaving,
  onSubmit,
}: Readonly<{
  isSaving: boolean;
  onSubmit: (feedback: EventFeedbackInput) => Promise<boolean>;
}>) {
  const [outcome, setOutcome] = useState<ResolutionOutcome | null>(null);
  const [actualEventLabel, setActualEventLabel] = useState("");
  const [routine, setRoutine] = useState<boolean | null>(null);
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!outcome || !actualEventLabel.trim() || routine === null) {
      setValidationMessage("Choose an outcome, describe what happened, and answer the routine question.");
      return;
    }

    setValidationMessage(null);
    await onSubmit({
      outcome,
      actualEventLabel: actualEventLabel.trim(),
      routine,
    });
  }

  return (
    <form className={styles.resolutionForm} onSubmit={(event) => void submit(event)}>
      <fieldset>
        <legend>What was the outcome?</legend>
        <div className={styles.outcomeOptions}>
          {outcomes.map((item) => (
            <label key={item.value}>
              <input
                type="radio"
                name="resolution-outcome"
                value={item.value}
                checked={outcome === item.value}
                onChange={() => setOutcome(item.value)}
              />
              <span><strong>{item.label}</strong><small>{item.description}</small></span>
            </label>
          ))}
        </div>
      </fieldset>

      <label className={styles.fieldLabel}>
        What actually happened?
        <input
          type="text"
          value={actualEventLabel}
          maxLength={120}
          placeholder="Example: Assisted movement"
          onChange={(event) => setActualEventLabel(event.target.value)}
        />
      </label>

      <fieldset>
        <legend>Was this part of the resident&apos;s normal routine?</legend>
        <div className={styles.inlineOptions}>
          <label><input type="radio" name="routine" checked={routine === true} onChange={() => setRoutine(true)} /> Yes</label>
          <label><input type="radio" name="routine" checked={routine === false} onChange={() => setRoutine(false)} /> No</label>
        </div>
      </fieldset>

      {validationMessage && <p className={styles.validationMessage} role="alert">{validationMessage}</p>}
      <button className={styles.primaryButton} type="submit" disabled={isSaving}>
        {isSaving ? "Saving resolution…" : "Resolve and save feedback"}
      </button>
    </form>
  );
}
