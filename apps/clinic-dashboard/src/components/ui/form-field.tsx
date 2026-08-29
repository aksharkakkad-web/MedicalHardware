import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

import styles from "./form-field.module.css";

export type FormFieldOption = Readonly<{
  value: string;
  label: string;
  disabled?: boolean;
}>;

type SharedFieldProps = Readonly<{
  id?: string;
  label: string;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  className?: string;
  "aria-describedby"?: string;
}>;

type InputFieldProps = SharedFieldProps &
  Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "aria-label" | "aria-describedby" | "aria-errormessage" | "required"> & {
    as?: "input";
  };

type TextareaFieldProps = SharedFieldProps &
  Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id" | "aria-label" | "aria-describedby" | "aria-errormessage" | "required"> & {
    as: "textarea";
  };

type SelectFieldProps = SharedFieldProps &
  Omit<SelectHTMLAttributes<HTMLSelectElement>, "id" | "aria-label" | "aria-describedby" | "aria-errormessage" | "required"> & {
    as: "select";
    options?: readonly FormFieldOption[];
  };

export type FormFieldProps = InputFieldProps | TextareaFieldProps | SelectFieldProps;

function mergeIds(...ids: Array<string | undefined>) {
  return Array.from(new Set(ids.filter(Boolean))).join(" ") || undefined;
}

const fieldOnlyProps = new Set(["as", "id", "label", "hint", "error", "className", "options", "children"]);

function nativeProps(props: FormFieldProps) {
  return Object.fromEntries(Object.entries(props).filter(([key]) => !fieldOnlyProps.has(key)));
}

export function FormField(props: FormFieldProps) {
  const generatedId = useId();
  const fieldId = props.id ?? generatedId;
  const hintId = props.hint ? `${fieldId}-hint` : undefined;
  const errorId = props.error ? `${fieldId}-error` : undefined;
  const describedBy = mergeIds(props["aria-describedby"], hintId, errorId);
  const invalid = Boolean(props.error) || props["aria-invalid"] === true || props["aria-invalid"] === "true";
  const fieldClassName = [styles.field, props.className].filter(Boolean).join(" ");
  const label = (
    <label className={styles.label} htmlFor={fieldId}>
      {props.label}
      {props.required ? <span className={styles.required}>Required</span> : null}
    </label>
  );
  const hint = props.hint ? <p className={styles.hint} id={hintId}>{props.hint}</p> : null;
  const error = props.error ? <p className={styles.error} id={errorId}>{props.error}</p> : null;

  if (props.as === "textarea") {
    return (
      <div className={fieldClassName}>
        {label}
        {hint}
        <textarea {...nativeProps(props)} id={fieldId} className={styles.control} required={props.required} aria-invalid={invalid || undefined} aria-describedby={describedBy} />
        {error}
      </div>
    );
  }

  if (props.as === "select") {
    return (
      <div className={fieldClassName}>
        {label}
        {hint}
        <select {...nativeProps(props)} id={fieldId} className={styles.control} required={props.required} aria-invalid={invalid || undefined} aria-describedby={describedBy}>
          {props.options?.map((option) => <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>)}
          {props.children}
        </select>
        {error}
      </div>
    );
  }

  return (
    <div className={fieldClassName}>
      {label}
      {hint}
      <input {...nativeProps(props)} id={fieldId} className={styles.control} required={props.required} aria-invalid={invalid || undefined} aria-describedby={describedBy} />
      {error}
    </div>
  );
}

export function FormFieldset({ legend, children, className }: Readonly<{ legend: string; children: ReactNode; className?: string }>) {
  return <fieldset className={[styles.fieldset, className].filter(Boolean).join(" ")}><legend>{legend}</legend>{children}</fieldset>;
}
