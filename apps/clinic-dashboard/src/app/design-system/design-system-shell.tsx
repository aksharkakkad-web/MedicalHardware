"use client";

import { useEffect, useRef, type ReactNode } from "react";

import styles from "./page.module.css";

function decodeHashTarget(hash: string) {
  if (!hash.startsWith("#") || hash.length < 2) return null;

  try {
    const targetId = decodeURIComponent(hash.slice(1));
    return targetId.length > 0 ? targetId : null;
  } catch {
    return null;
  }
}

export function DesignSystemShell({ children }: Readonly<{ children: ReactNode }>) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const pageRoot = rootRef.current;
    if (!pageRoot) return;

    const sectionLinks = Array.from(
      pageRoot.querySelectorAll<HTMLAnchorElement>('aside nav a[href^="#section-"]'),
    );
    const sections = Array.from(pageRoot.querySelectorAll<HTMLElement>("section[id^='section-']"));
    const index = pageRoot.querySelector<HTMLElement>("[data-design-system-index]");
    const getTarget = (hash: string) => {
      const targetId = decodeHashTarget(hash);
      if (!targetId) return null;
      return Array.from(pageRoot.querySelectorAll<HTMLElement>("[id]"))
        .find((element) => element.id === targetId) ?? null;
    };
    const setActiveSection = (sectionId: string | null) => {
      sectionLinks.forEach((link) => {
        const active = sectionId !== null && link.getAttribute("href") === `#${sectionId}`;
        if (active) link.setAttribute("aria-current", "true");
        else link.removeAttribute("aria-current");
      });
    };
    const getStickyOffset = () => {
      const measuredHeight = index?.offsetHeight ?? 0;
      return (measuredHeight > 0 ? measuredHeight : 0) + 16;
    };
    const scrollToTarget = (target: HTMLElement, behavior: ScrollBehavior) => {
      const stickyOffset = getStickyOffset();
      const rootTop = pageRoot.getBoundingClientRect().top;
      const top = pageRoot.scrollTop + target.getBoundingClientRect().top - rootTop - stickyOffset;
      if (typeof pageRoot.scrollTo === "function") pageRoot.scrollTo({ top, behavior });
      else pageRoot.scrollTop = top;
    };
    const scrollRootToTop = () => {
      if (typeof pageRoot.scrollTo === "function") pageRoot.scrollTo({ top: 0, behavior: "auto" });
      else pageRoot.scrollTop = 0;
    };
    const focusTarget = (target: HTMLElement) => {
      target.focus({ preventScroll: true });
    };
    const navigateToHash = (hash: string, behavior: ScrollBehavior = "auto") => {
      const target = getTarget(hash);
      if (!target) {
        setActiveSection(null);
        return false;
      }

      const section = target.closest<HTMLElement>("section[id^='section-']");
      setActiveSection(section?.id ?? null);
      scrollToTarget(target, behavior);
      focusTarget(target);
      return true;
    };

    const handleAnchorClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const clickedElement = event.target;
      if (!(clickedElement instanceof Element)) return;
      const anchor = clickedElement.closest<HTMLAnchorElement>('a[href^="#"]');
      if (!anchor || !pageRoot.contains(anchor)) return;
      const hash = anchor.getAttribute("href") ?? "";
      if (!getTarget(hash)) return;
      event.preventDefault();
      window.history.pushState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
      navigateToHash(hash);
    };

    const handleHashNavigation = () => {
      if (!window.location.hash) {
        setActiveSection("section-01");
        scrollRootToTop();
        return;
      }
      navigateToHash(window.location.hash);
    };
    const sectionObserver = typeof IntersectionObserver === "function"
      ? new IntersectionObserver(
          (entries) => {
            const visible = entries
              .filter((entry) => entry.isIntersecting)
              .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
            const current = visible[0]?.target as HTMLElement | undefined;
            if (current) setActiveSection(current.id);
          },
          { root: pageRoot, rootMargin: "-18% 0px -72% 0px", threshold: 0 },
        )
      : null;

    setActiveSection("section-01");
    sections.forEach((section) => sectionObserver?.observe(section));
    pageRoot.addEventListener("click", handleAnchorClick);
    window.addEventListener("hashchange", handleHashNavigation);
    window.addEventListener("popstate", handleHashNavigation);
    if (window.location.hash) requestAnimationFrame(() => navigateToHash(window.location.hash));

    return () => {
      pageRoot.removeEventListener("click", handleAnchorClick);
      window.removeEventListener("hashchange", handleHashNavigation);
      window.removeEventListener("popstate", handleHashNavigation);
      sectionObserver?.disconnect();
    };
  }, []);

  return (
    <div className={styles.viewport} ref={rootRef}>
      {children}
    </div>
  );
}
