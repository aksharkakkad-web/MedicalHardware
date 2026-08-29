import { fireEvent, render, screen } from "@testing-library/react";
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
        <nav>
          <a href="#section-01">Foundation</a>
          <a href="#section-02">Color</a>
        </nav>
      </aside>
      <main id="design-system-content" tabIndex={-1}>
        <section id="section-01" tabIndex={-1}>Foundation specimens</section>
        <section id="section-02" tabIndex={-1}>Color specimens</section>
      </main>
    </DesignSystemShell>,
  );
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

  it("keeps static loading and success specimens semantically honest", () => {
    render(<DesignSystemPage />);

    expect(screen.getByRole("button", { name: /saving change/i })).toBeDisabled();
    expect(screen.getByText("Saved")).not.toHaveAttribute("role", "status");
    expect(Array.from(document.querySelectorAll("button")).every((button) => button.type === "button")).toBe(true);
  });
});
