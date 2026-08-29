"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { HomeIcon, RoutineIcon, UpdateIcon } from "@/components/icons";
import styles from "./home-shell.module.css";

const destinations = [
  { href: "/", label: "Today", icon: HomeIcon, match: (path: string) => path === "/" },
  { href: "/updates/home_evt_unusual_001", label: "Updates", icon: UpdateIcon, match: (path: string) => path.startsWith("/updates") },
  { href: "/routines", label: "Routines", icon: RoutineIcon, match: (path: string) => path.startsWith("/routines") },
];

export function HomeShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return <div className={styles.frame}>
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link href="/" className={styles.brand} aria-label="Adaptive Care Home">
          <span className={styles.brandMark}>A</span>
          <span><strong>Adaptive Care</strong><small>Home</small></span>
        </Link>
        <nav className={styles.desktopNav} aria-label="Main navigation">
          {destinations.map(({ href, label, match }) => <Link key={href} href={href} className={match(pathname) ? styles.activeLink : undefined} aria-current={match(pathname) ? "page" : undefined}>{label}</Link>)}
        </nav>
        <span className={styles.demoBadge}>Synthetic demo</span>
      </div>
    </header>
    <main className={styles.main}>{children}</main>
    <footer className={styles.footer}>This demo shows monitoring information, not medical advice or an emergency service.</footer>
    <nav className={styles.mobileNav} aria-label="Main navigation">
      {destinations.map(({ href, label, icon: Icon, match }) => <Link key={href} href={href} className={match(pathname) ? styles.mobileActive : undefined} aria-current={match(pathname) ? "page" : undefined}><Icon/><span>{label}</span></Link>)}
    </nav>
  </div>;
}
