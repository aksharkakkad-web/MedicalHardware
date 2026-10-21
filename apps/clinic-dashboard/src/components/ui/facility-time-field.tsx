"use client";

import { useId } from "react";
import { facilityDateTimeCandidates, facilityDateTimeInputValue } from "@/lib/facility-time";
import { FormField, FormFieldset } from "./form-field";
import styles from "./facility-time-field.module.css";
export interface FacilityTimeFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  timeZone: string;
  required?: boolean;
  disabled?: boolean;
  hint?: string;
}
function abbreviation(iso: string, timeZone: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "short"
  }).formatToParts(new Date(iso)).find(part => part.type === "timeZoneName")?.value ?? timeZone;
}
/** Local wall-time entry; only unique or explicitly chosen instants are emitted with a timezone. */
export function FacilityTimeField({
  label,
  value,
  onChange,
  timeZone,
  required,
  disabled,
  hint
}: FacilityTimeFieldProps) {
  const groupId = useId();
  const formatted = facilityDateTimeInputValue(value, timeZone);
  const local = formatted || value;
  const candidates = facilityDateTimeCandidates(local, timeZone);
  const explicit = Boolean(formatted);
  const minute = (timestamp: string) => Math.floor(Date.parse(timestamp) / 60_000);
  const selected = explicit ? candidates.findIndex(candidate => minute(candidate) === minute(value)) : -1;
  const repeated = candidates.length > 1;
  const error = !value ? "" : !candidates.length ? "This date or time does not exist in the facility’s time zone. Choose a valid date and time." : repeated && selected < 0 ? "This time occurs twice when the clocks change. Choose the first or second occurrence." : "";
  function change(localValue: string) {
    const options = facilityDateTimeCandidates(localValue, timeZone);
    onChange(options.length === 1 ? options[0] : localValue);
  }
  return <div className={styles.field}>
      <FormField label={label} type="datetime-local" value={local} required={required} disabled={disabled} onChange={event => change(event.target.value)} hint={`${hint ? hint + " " : ""}Use the facility’s time zone (${timeZone.replace(/_/g, " ")}).`} error={error ? <span role="alert">{error}</span> : undefined} />
      {repeated ? <FormFieldset legend={`${label}: choose occurrence`} className={styles.occurrences}>
          {candidates.map((candidate, index) => <label key={candidate} className={styles.choice}>
              <input type="radio" name={groupId} value={candidate} checked={selected === index} disabled={disabled} required onChange={() => onChange(candidate)} />
              <span>
                {index === 0 ? "First" : "Second"} occurrence ·{" "}
                {abbreviation(candidate, timeZone)}
              </span>
            </label>)}
        </FormFieldset> : null}
    </div>;
}
