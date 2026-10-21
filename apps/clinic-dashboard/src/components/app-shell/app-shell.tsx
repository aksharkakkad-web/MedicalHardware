"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  OverviewIcon,
  ResidentsIcon,
  EventIcon,
  ScenarioIcon,
  DeviceIcon,
} from "@/components/icons/icons";
import { useWorkspace } from "@/lib/workspace";
import styles from "./app-shell.module.css";

const destinations = [
  { label: "Overview", href: "/", icon: OverviewIcon },
  { label: "Residents", href: "/residents", icon: ResidentsIcon },
  { label: "Handover", href: "/handover", icon: ScenarioIcon },
  { label: "Events", href: "/events", icon: EventIcon },
];

function SyrenSymbol() {
  return (
    <svg viewBox="0 0 28 28" aria-hidden="true" fill="none">
      <path
        d="M21 6H11a5 5 0 0 0 0 10h6a3 3 0 0 1 0 6H7"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M7 6v6M21 16v6"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const { snapshot, status, client } = useWorkspace();
  const [areaError, setAreaError] = useState<string | null>(null);
  const [changingArea, setChangingArea] = useState(false);
  if (pathname.startsWith("/design-system")) return children;
  const areas =
    snapshot?.areas.filter((area) =>
      snapshot.currentClient.areaIds.includes(area.areaId),
    ) ?? [];
  const area = areas.find((item) => item.areaId === snapshot?.currentAreaId);
  const revoked = snapshot?.currentClient.status === "revoked";

  async function changeArea(areaId: string) {
    setAreaError(null);
    setChangingArea(true);
    try {
      await client.setCurrentArea(areaId);
    } catch (error) {
      setAreaError(
        error instanceof Error
          ? error.message
          : "The area could not be changed. Try again.",
      );
    } finally {
      setChangingArea(false);
    }
  }

  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#care-workspace">
        Skip to workspace
      </a>
      <aside className={styles.sidebar}>
        <Link href="/" className={styles.brand} aria-label="SYREN overview">
          <span className={styles.brandMark}>
            <SyrenSymbol />
          </span>
          <span>
            <strong className={styles.brandName}>SYREN</strong>
            <span className={styles.brandSubtitle}>Care workspace</span>
          </span>
        </Link>
        <nav className={styles.navigation} aria-label="Care workspace">
          <p className={styles.navigationLabel}>Workspace</p>
          <ul className={styles.navigationList}>
            {destinations.map(({ label, href, icon: NavIcon }) => {
              const active =
                href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <li key={href}>
                  <Link
                    className={active ? styles.activeLink : styles.navLink}
                    href={href}
                    aria-current={active ? "page" : undefined}
                  >
                    <NavIcon className={styles.navIcon} />
                    <span>{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <nav className={styles.facilityNavigation} aria-label="Facility tools">
          <p className={styles.navigationLabel}>Facility</p>
          <Link
            className={
              pathname.startsWith("/station")
                ? styles.activeLink
                : styles.navLink
            }
            href="/station"
          >
            <DeviceIcon className={styles.navIcon} />
            <span>Shared devices</span>
          </Link>
          <Link
            className={
              pathname.startsWith("/imports")
                ? styles.activeLink
                : styles.navLink
            }
            href="/imports"
          >
            <ResidentsIcon className={styles.navIcon} />
            <span>Directory imports</span>
          </Link>
          <Link className={styles.navLink} href="/devices">
            <OverviewIcon className={styles.navIcon} />
            <span>Monitoring status</span>
          </Link>
        </nav>
        <div className={styles.sidebarFooter}>
          <div className={styles.environment}>
            <span className={styles.demoDot} />
            <strong>Demo workspace</strong>
          </div>
          <p className={styles.footerNote}>Synthetic residents</p>
          <p className={styles.footerDetail}>
            No live monitoring or alert delivery.
          </p>
          <details className={styles.developerTools}>
            <summary>Demo tools</summary>
            <Link href="/scenarios">Scenario lab</Link>
            <Link href="/design-system">Design system</Link>
          </details>
        </div>
      </aside>
      <section className={styles.workspace}>
        <header className={styles.topbar} aria-label="Current care workspace">
          <div className={styles.facilityContext}>
            <span className={styles.workspaceName}>
              {snapshot?.facility.name ?? "Care workspace"}
            </span>
            <span className={styles.contextDivider}>/</span>
            <label className={styles.areaLabel}>
              <span className={styles.srOnly}>Monitoring area</span>
              <select
                aria-label="Monitoring area"
                value={snapshot?.currentAreaId ?? ""}
                disabled={!snapshot || changingArea || revoked}
                onChange={(event) => void changeArea(event.target.value)}
                className={styles.areaSelect}
              >
                {!snapshot && <option value="">Loading area…</option>}
                {snapshot && <option value="all">All covered areas</option>}
                {areas.map((item) => (
                  <option key={item.areaId} value={item.areaId}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className={styles.topbarActions}>
            <span className={styles.tabletDemo}>Demo · no live alerts</span>
            <Link className={styles.stationLink} href="/station">
              <span className={styles.stationDot} />
              <span>
                {snapshot?.currentClient.name ??
                  (status === "error"
                    ? "Connection unavailable"
                    : "Shared station")}
              </span>
            </Link>
            <Link
              href="/administration"
              className={
                snapshot?.admin.active ? styles.adminActive : styles.adminLink
              }
            >
              Administration{snapshot?.admin.active && <span> · Demo</span>}
            </Link>
          </div>
        </header>
        {areaError && (
          <p className={styles.areaError} role="alert">
            {areaError}
          </p>
        )}
        <div className={styles.mobileContext}>
          <span>
            {snapshot?.currentAreaId === "all"
              ? "All covered areas"
              : (area?.name ?? "Shared workspace")}
          </span>
          <span>Demo · no live alerts</span>
        </div>
        <main
          id="care-workspace"
          tabIndex={-1}
          className={
            pathname === "/"
              ? `${styles.main} ${styles.overviewMain}`
              : styles.main
          }
        >
          {revoked &&
          !["/station", "/administration", "/notifications"].includes(
            pathname,
          ) ? (
            <section className={styles.accessState}>
              <p className={styles.navigationLabel}>Shared access</p>
              <h1>This device is no longer approved</h1>
              <p>
                An administrator needs to approve this shared device before it
                can display resident information.
              </p>
              <Link href="/station">Review shared access</Link>
            </section>
          ) : (
            children
          )}
        </main>
      </section>
    </div>
  );
}
