"use client";

import { useEffect, useRef, type ReactNode } from "react";

import styles from "./page.module.css";

export function DesignSystemShell({ children }: Readonly<{ children: ReactNode }>) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const pageRoot = rootRef.current;
    const appMain = rootRef.current?.closest("main");
    const appTopbar = appMain?.previousElementSibling as HTMLElement | null;
    const appSidebar = appMain?.parentElement?.previousElementSibling as HTMLElement | null;
    const hiddenElements = [appTopbar, appSidebar].filter(
      (element): element is HTMLElement => element !== null,
    );

    hiddenElements.forEach((element) => {
      element.inert = true;
      element.setAttribute("aria-hidden", "true");
    });

    const scrollToHash = (hash: string, behavior: ScrollBehavior) => {
      if (!pageRoot || !hash.startsWith("#")) return;
      const target = pageRoot.querySelector<HTMLElement>(hash);
      if (!target) return;
      const stickyOffset = window.matchMedia("(max-width: 980px)").matches ? 58 : 16;
      const top = pageRoot.scrollTop + target.getBoundingClientRect().top - stickyOffset;
      pageRoot.scrollTo({ top, behavior });
    };

    const handleAnchorClick = (event: MouseEvent) => {
      const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>('a[href^="#"]');
      if (!anchor) return;
      event.preventDefault();
      const hash = anchor.getAttribute("href") ?? "";
      window.history.replaceState(null, "", hash);
      scrollToHash(hash, "auto");
    };

    const sectionLinks = Array.from(
      pageRoot?.querySelectorAll<HTMLAnchorElement>('aside nav a[href^="#section-"]') ?? [],
    );
    const setActiveSection = (sectionId: string) => {
      sectionLinks.forEach((link) => {
        const active = link.getAttribute("href") === `#${sectionId}`;
        if (active) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
    };
    setActiveSection("section-01");

    const sectionObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        const current = visible[0]?.target as HTMLElement | undefined;
        if (current) setActiveSection(current.id);
      },
      { root: pageRoot, rootMargin: "-18% 0px -72% 0px", threshold: 0 },
    );
    pageRoot?.querySelectorAll<HTMLElement>("section[id^='section-']").forEach((section) => {
      sectionObserver.observe(section);
    });

    pageRoot?.addEventListener("click", handleAnchorClick);
    if (window.location.hash) requestAnimationFrame(() => scrollToHash(window.location.hash, "auto"));

    return () => {
      pageRoot?.removeEventListener("click", handleAnchorClick);
      sectionObserver.disconnect();
      hiddenElements.forEach((element) => {
        element.inert = false;
        element.removeAttribute("aria-hidden");
      });
    };
  }, []);

  return (
    <div className={styles.viewport} ref={rootRef}>
      {children}
    </div>
  );
}
