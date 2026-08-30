import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DesignSystemShell } from "./design-system-shell";
import DesignSystemPage from "./page";

class IntersectionObserverStub {
  observe = vi.fn();
  disconnect = vi.fn();

  constructor(...args: unknown[]) {
    void args;
  }
}

function renderShell() {
  return render(
    <DesignSystemShell>
      <a href="#design-system-content">Skip to specimens</a>
      <aside aria-label="Design system sections" data-design-system-index>
        <div>
          <nav data-design-system-nav>
            <a href="#section-01">Foundation</a>
            <a href="#section-02">Color</a>
          </nav>
          <span data-design-system-nav-fade aria-hidden="true" hidden />
          <button type="button" data-design-system-more aria-label="More design system sections" hidden>More sections</button>
        </div>
      </aside>
      <main id="design-system-content" tabIndex={-1}>
        <section id="section-01" tabIndex={-1}>Foundation specimens</section>
        <section id="section-02" tabIndex={-1}>Color specimens</section>
      </main>
    </DesignSystemShell>,
  );
}

function setNavMetrics({ clientWidth, scrollWidth, scrollLeft = 0 }: { clientWidth: number; scrollWidth: number; scrollLeft?: number }) {
  const nav = document.querySelector<HTMLElement>("[data-design-system-nav]");
  if (!nav) throw new Error("section navigation is missing");
  Object.defineProperties(nav, {
    clientWidth: { configurable: true, value: clientWidth },
    scrollWidth: { configurable: true, value: scrollWidth },
    scrollLeft: { configurable: true, writable: true, value: scrollLeft },
  });
  return nav;
}

function setLinkMetrics(link: HTMLElement, { left, width, offsetLeft = left, offsetWidth = width }: { left: number; width: number; offsetLeft?: number; offsetWidth?: number }) {
  vi.spyOn(link, "getBoundingClientRect").mockReturnValue({
    bottom: 44,
    height: 44,
    left,
    right: left + width,
    top: 0,
    width,
    x: left,
    y: 0,
    toJSON: () => ({}),
  });
  Object.defineProperties(link, {
    offsetLeft: { configurable: true, value: offsetLeft },
    offsetWidth: { configurable: true, value: offsetWidth },
  });
}

describe("DesignSystemShell", () => {
  beforeEach(() => {
    vi.stubGlobal("IntersectionObserver", IntersectionObserverStub);
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      callback(0);
      return 0;
    });
    window.history.replaceState(null, "", "/design-system");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("moves focus to the single content landmark when skip navigation is activated", () => {
    renderShell();
    const content = screen.getByRole("main");

    fireEvent.click(screen.getByRole("link", { name: /skip to specimens/i }));

    expect(content).toHaveAttribute("tabindex", "-1");
    expect(document.activeElement).toBe(content);
  });

  it("ignores malformed and unknown hashes without throwing", () => {
    renderShell();

    expect(() => {
      fireEvent.click(screen.getByRole("link", { name: "Color" }));
      window.history.replaceState(null, "", "/design-system#%E0%A4%A");
      fireEvent(window, new HashChangeEvent("hashchange"));
      window.history.replaceState(null, "", "/design-system#not-present");
      fireEvent(window, new PopStateEvent("popstate"));
    }).not.toThrow();

    expect(document.activeElement).not.toBe(screen.getByRole("main"));
    expect(screen.getByRole("link", { name: "Foundation" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Color" })).not.toHaveAttribute("aria-current");
  });

  it("updates active state, hash, scroll, and focus immediately for section navigation", () => {
    renderShell();
    const viewport = screen.getByRole("main").parentElement;
    const destination = screen.getByText("Color specimens");
    const scrollTo = vi.fn();
    const focus = vi.spyOn(destination, "focus");
    const index = document.querySelector<HTMLElement>("[data-design-system-index]");
    Object.defineProperty(index, "offsetHeight", { configurable: true, value: 61 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 0, writable: true });
    Object.defineProperty(viewport, "scrollTo", { configurable: true, value: scrollTo });
    vi.spyOn(destination, "getBoundingClientRect").mockReturnValue({
      bottom: 220,
      height: 200,
      left: 0,
      right: 640,
      top: 180,
      width: 640,
      x: 0,
      y: 180,
      toJSON: () => ({}),
    });

    fireEvent.click(screen.getByRole("link", { name: "Color" }));

    expect(window.location.hash).toBe("#section-02");
    expect(screen.getByRole("link", { name: "Color" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("link", { name: "Foundation" })).not.toHaveAttribute("aria-current");
    expect(scrollTo).toHaveBeenCalledWith({ top: 103, behavior: "auto" });
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(document.activeElement).toBe(destination);
  });

  it("responds to hashchange and popstate by selecting and focusing known sections", () => {
    renderShell();
    const destination = screen.getByText("Color specimens");
    const firstSection = screen.getByText("Foundation specimens");
    const focus = vi.spyOn(destination, "focus");
    const firstFocus = vi.spyOn(firstSection, "focus");

    window.history.replaceState(null, "", "/design-system#section-02");
    fireEvent(window, new HashChangeEvent("hashchange"));

    expect(screen.getByRole("link", { name: "Color" })).toHaveAttribute("aria-current", "true");
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });

    focus.mockClear();
    window.history.replaceState(null, "", "/design-system#section-01");
    fireEvent(window, new PopStateEvent("popstate"));

    expect(screen.getByRole("link", { name: "Foundation" })).toHaveAttribute("aria-current", "true");
    expect(firstFocus).toHaveBeenCalledWith({ preventScroll: true });
  });

  it("reveals the active link for a deep hash without scrolling the page", () => {
    const animationFrames: FrameRequestCallback[] = [];
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      animationFrames.push(callback);
      return animationFrames.length;
    });
    window.history.replaceState(null, "", "/design-system#section-02");
    renderShell();
    const nav = setNavMetrics({ clientWidth: 120, scrollWidth: 360 });
    const navScrollTo = vi.fn();
    Object.defineProperty(nav, "scrollTo", { configurable: true, value: navScrollTo });
    setLinkMetrics(screen.getByRole("link", { name: "Color" }), { left: 150, width: 64 });
    animationFrames.forEach((callback) => callback(0));

    expect(screen.getByRole("link", { name: "Color" })).toHaveAttribute("aria-current", "true");
    expect(navScrollTo).toHaveBeenCalledWith({ left: 94, behavior: "auto" });
    expect(navScrollTo).not.toHaveBeenCalledWith(expect.objectContaining({ top: expect.anything() }));
  });

  it("reveals an active link from click and hash listeners while retaining the horizontal fallback", () => {
    renderShell();
    const nav = setNavMetrics({ clientWidth: 120, scrollWidth: 360 });
    Object.defineProperty(nav, "scrollTo", { configurable: true, value: undefined });
    const colorLink = screen.getByRole("link", { name: "Color" });
    setLinkMetrics(colorLink, { left: 150, width: 64 });

    fireEvent.click(colorLink);

    expect(colorLink).toHaveAttribute("aria-current", "true");
    expect(nav.scrollLeft).toBe(94);
  });

  it("keeps the active link inside the usable nav area beside the More sections cue", () => {
    renderShell();
    const nav = setNavMetrics({ clientWidth: 390, scrollWidth: 780 });
    nav.style.paddingRight = "128px";
    vi.spyOn(nav, "getBoundingClientRect").mockReturnValue({
      bottom: 44,
      height: 44,
      left: 0,
      right: 390,
      top: 0,
      width: 390,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    const more = document.querySelector<HTMLButtonElement>("[data-design-system-more]");
    if (!more) throw new Error("more sections cue is missing");
    vi.spyOn(more, "getBoundingClientRect").mockReturnValue({
      bottom: 44,
      height: 44,
      left: 262,
      right: 390,
      top: 0,
      width: 128,
      x: 262,
      y: 0,
      toJSON: () => ({}),
    });
    fireEvent(window, new Event("resize"));
    const navScrollTo = vi.fn();
    Object.defineProperty(nav, "scrollTo", { configurable: true, value: navScrollTo });
    const colorLink = screen.getByRole("link", { name: "Color" });
    setLinkMetrics(colorLink, { left: 320, width: 96 });

    fireEvent.click(colorLink);

    const nextScrollLeft = navScrollTo.mock.calls[0]?.[0].left as number;
    const usableWidth = nav.clientWidth - 128;
    expect(nextScrollLeft).toBe(154);
    expect(nextScrollLeft).toBeLessThanOrEqual(320);
    expect(nextScrollLeft + usableWidth).toBeGreaterThanOrEqual(416);
  });

  it("restores the first section and root scroll when history returns to an empty hash", () => {
    renderShell();
    const viewport = screen.getByRole("main").parentElement;
    const destination = screen.getByText("Color specimens");
    const destinationFocus = vi.spyOn(destination, "focus");
    const scrollTo = vi.fn();
    Object.defineProperty(viewport, "scrollTo", { configurable: true, value: scrollTo });

    fireEvent.click(screen.getByRole("link", { name: "Color" }));
    destinationFocus.mockClear();
    window.history.replaceState(null, "", "/design-system");
    fireEvent(window, new PopStateEvent("popstate"));

    expect(screen.getByRole("link", { name: "Foundation" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("link", { name: "Color" })).not.toHaveAttribute("aria-current");
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: "auto" });
    expect(destinationFocus).not.toHaveBeenCalled();
  });

  it("shows the more-sections cue when the section navigation initially overflows", () => {
    renderShell();
    setNavMetrics({ clientWidth: 160, scrollWidth: 520 });
    fireEvent(window, new Event("resize"));

    expect(screen.getByRole("button", { name: /more design system sections/i })).not.toHaveAttribute("hidden");
    expect(document.querySelector("[data-design-system-nav-fade]")).not.toHaveAttribute("hidden");
  });

  it("scrolls the section navigation forward and hides the cue at the end", () => {
    renderShell();
    const nav = setNavMetrics({ clientWidth: 160, scrollWidth: 520 });
    fireEvent(window, new Event("resize"));
    const more = screen.getByRole("button", { name: /more design system sections/i });

    fireEvent.click(more);
    expect(nav.scrollLeft).toBeGreaterThan(0);

    nav.scrollLeft = 360;
    fireEvent(nav, new Event("scroll"));
    expect(more).toHaveAttribute("hidden");
    expect(document.querySelector("[data-design-system-nav-fade]")).toHaveAttribute("hidden");
  });

  it("updates overflow visibility on resize and cleans up listeners on unmount", () => {
    const removeEventListener = vi.spyOn(window, "removeEventListener");
    const view = renderShell();
    const nav = setNavMetrics({ clientWidth: 240, scrollWidth: 200 });
    fireEvent(window, new Event("resize"));
    expect(document.querySelector("[data-design-system-more]")).toHaveAttribute("hidden");

    Object.defineProperty(nav, "scrollWidth", { configurable: true, value: 500 });
    fireEvent(window, new Event("resize"));
    expect(document.querySelector("[data-design-system-more]")).not.toHaveAttribute("hidden");

    view.unmount();
    expect(removeEventListener).toHaveBeenCalledWith("resize", expect.any(Function));
  });

  it("keeps static loading and success specimens semantically honest", () => {
    render(<DesignSystemPage />);

    expect(screen.getByRole("button", { name: /saving change/i })).toBeDisabled();
    expect(screen.getByText("Saved")).not.toHaveAttribute("role", "status");
    const residentTable = screen.getByRole("table", { name: /synthetic resident monitoring records/i });
    expect(within(residentTable).getAllByRole("row")).toHaveLength(6);
    expect(screen.getAllByText("Hover example")).toHaveLength(2);
    expect(screen.getAllByText("Selected record")).toHaveLength(2);
    expect(within(residentTable).getAllByText("Selected record")).toHaveLength(1);
    const residentRows = within(residentTable).getAllByRole("row").slice(1);
    const roomLabels = residentRows.map((row) => row.querySelector("[data-record-identity] span")?.textContent?.trim()).filter(Boolean);
    expect(new Set(roomLabels).size).toBe(roomLabels.length);
    expect(residentRows[1]).toHaveAttribute("data-interaction", "hover");
    expect(residentRows[2]).toHaveAttribute("data-interaction", "selected");
    expect(residentRows[3]).not.toHaveAttribute("data-interaction");
    expect(residentRows[3]).toHaveTextContent("Watch attention priority");
    expect(residentRows[4]).not.toHaveAttribute("data-interaction");
    expect(residentRows[4]).toHaveTextContent("Critical attention priority");
    expect(Array.from(document.querySelectorAll("button")).every((button) => button.type === "button")).toBe(true);
  });
});
