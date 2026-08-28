"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { CareMark, EventIcon, OverviewIcon } from "@/components/icons/icons";

import styles from "./app-shell.module.css";

const destinations = [
  { label: "Overview", href: "/", icon: OverviewIcon },
  { label: "Events", href: "/events", icon: EventIcon },
];

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  return (
    <div className={styles.shell}>
      <header className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandMark}><CareMark /></span>
          <span>
            <strong className={styles.brandName}>Adaptive Care</strong>
            <span className={styles.brandSubtitle}>Clinic console</span>
          </span>
        </div>

        <nav className={styles.navigation} aria-label="Clinic navigation">
          <ul className={styles.navigationList}>
            {destinations.map(({ label, href, icon: NavIcon }) => {
              const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
              <li key={href}>
                <Link className={active ? styles.activeLink : styles.navLink} href={href} aria-current={active ? "page" : undefined}>
                  <NavIcon className={styles.navIcon} />
                  <span>{label}</span>
                </Link>
              </li>
              );
            })}
          </ul>
        </nav>

        <div className={styles.sidebarFooter}>
          <span className={styles.demoDot} aria-hidden="true" />
          <div><p className={styles.footerLabel}>Synthetic demo</p><p className={styles.footerNote}>No real resident information</p></div>
        </div>
      </header>

      <section className={styles.workspace}>
        <div className={styles.topbar}>
          <div>
            <p className={styles.workspaceName}>Northstar Clinic</p>
            <p className={styles.workspaceMeta}>Operations workspace</p>
          </div>
          <span className={styles.demoBadge}>Synthetic demo data</span>
        </div>
        <main className={styles.main}>{children}</main>
      </section>
    </div>
  );
}
