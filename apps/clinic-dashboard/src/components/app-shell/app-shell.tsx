import Link from "next/link";
import type { ReactNode } from "react";

import { StatusPill } from "@/components/status-pill/status-pill";

import styles from "./app-shell.module.css";

const futureDestinations = ["Events", "Devices", "Settings"];

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className={styles.shell}>
      <header className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">
            AC
          </span>
          <span>
            <strong className={styles.brandName}>Adaptive Care</strong>
            <span className={styles.brandSubtitle}>Clinic console</span>
          </span>
        </div>

        <nav className={styles.navigation} aria-label="Clinic navigation">
          <ul className={styles.navigationList}>
            <li>
              <Link className={styles.activeLink} href="/" aria-current="page">
                <span className={styles.navIcon} aria-hidden="true">
                  R
                </span>
                <span>Residents</span>
              </Link>
            </li>
            {futureDestinations.map((destination) => (
              <li key={destination}>
                <span className={styles.futureItem} aria-disabled="true">
                  <span className={styles.navIcon} aria-hidden="true">
                    {destination.charAt(0)}
                  </span>
                  <span>{destination}</span>
                  <span className={styles.soon}>Soon</span>
                </span>
              </li>
            ))}
          </ul>
        </nav>

        <div className={styles.sidebarFooter}>
          <p className={styles.footerLabel}>Workspace</p>
          <StatusPill label="Synthetic data" tone="neutral" />
          <p className={styles.footerNote}>No real resident information</p>
        </div>
      </header>

      <section className={styles.workspace}>
        <div className={styles.topbar}>
          <div>
            <p className={styles.eyebrow}>Clinic operations</p>
            <p className={styles.workspaceName}>Northstar demo clinic</p>
          </div>
          <StatusPill label="Dashboard online" tone="healthy" />
        </div>
        <main className={styles.main}>{children}</main>
      </section>
    </div>
  );
}
