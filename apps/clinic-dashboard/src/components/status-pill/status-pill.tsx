import styles from "./status-pill.module.css";

export type StatusTone =
  | "neutral"
  | "healthy"
  | "attention"
  | "critical"
  | "unavailable";

export function StatusPill({
  label,
  tone,
}: Readonly<{ label: string; tone: StatusTone }>) {
  return (
    <span className={`${styles.pill} ${styles[tone]}`}>
      <span className={styles.dot} aria-hidden="true" />
      {label}
    </span>
  );
}
