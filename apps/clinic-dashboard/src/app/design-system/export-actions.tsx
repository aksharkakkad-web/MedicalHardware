"use client";

import styles from "./page.module.css";

export function ExportActions() {
  return (
    <div className={styles.exportActions} aria-label="Download design system">
      <a href="/downloads/syren-design-system.md" download>
        Download text guide
      </a>
      <button type="button" onClick={() => window.print()}>
        Print / Save as PDF
      </button>
    </div>
  );
}
