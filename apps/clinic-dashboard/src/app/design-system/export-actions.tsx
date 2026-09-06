"use client";

import styles from "./page.module.css";

export function ExportActions() {
  return (
    <div className={styles.exportActions} aria-label="Download design system">
      <a href="/downloads/adaptive-care-clear-signal-design-system.pdf" download>
        Download PDF
      </a>
      <a href="/downloads/adaptive-care-design-system.md" download>
        Download text guide
      </a>
      <button type="button" onClick={() => window.print()}>
        Print / Save as PDF
      </button>
    </div>
  );
}
