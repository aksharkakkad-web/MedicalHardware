import { readFileSync } from "node:fs";
import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { describe, expect, it } from "vitest";

import { LiquidGlassCard } from "./liquid-glass-card";

const cardStyles = readFileSync(
  "src/components/ui/liquid-glass-card.module.css",
  "utf8",
);

describe("LiquidGlassCard", () => {
  it("defaults to a neutral, non-interactive surface without mounting an SVG filter", () => {
    const { container } = render(
      <LiquidGlassCard aria-label="Welcome message" className="showcase-card">
        A calmer view of today
      </LiquidGlassCard>,
    );

    const card = screen.getByLabelText("Welcome message");
    expect(card).toHaveTextContent("A calmer view of today");
    expect(card).toHaveClass("showcase-card");
    expect(card).toHaveAttribute("data-glass-effect", "off");
    expect(card).toHaveAttribute("data-size", "default");
    expect(card).not.toHaveAttribute("role");
    expect(card).not.toHaveAttribute("tabindex");
    expect(container.querySelector("svg")).not.toBeInTheDocument();
    expect(container.querySelector("filter")).not.toBeInTheDocument();
  });

  it("uses a namespaced, instance-safe React id only when the effect is enabled", () => {
    const { container } = render(
      <>
        <LiquidGlassCard glassEffect>First</LiquidGlassCard>
        <LiquidGlassCard glassEffect>Second</LiquidGlassCard>
      </>,
    );

    const filters = Array.from(container.querySelectorAll("filter"));
    const refractions = Array.from(
      container.querySelectorAll<HTMLElement>("[data-liquid-glass-refraction]"),
    );
    const ids = filters.map((filter) => filter.id);

    expect(filters).toHaveLength(2);
    expect(refractions).toHaveLength(2);
    expect(ids[0]).toMatch(/^ac-liquid-glass-/);
    expect(ids[1]).toMatch(/^ac-liquid-glass-/);
    expect(new Set(ids).size).toBe(2);
    expect(refractions[0].style.backdropFilter).toContain(`#${ids[0]}`);
    expect(refractions[1].style.backdropFilter).toContain(`#${ids[1]}`);
  });

  it("supports the compact spacing size, native div attributes, and forwarded refs", () => {
    const ref = createRef<HTMLDivElement>();

    render(
      <LiquidGlassCard ref={ref} size="small" id="future-showcase">
        Preview
      </LiquidGlassCard>,
    );

    expect(ref.current).toBe(document.getElementById("future-showcase"));
    expect(ref.current).toHaveAttribute("data-size", "small");
  });

  it("uses only current Clear Signal tokens and includes accessibility fallbacks", () => {
    expect(cardStyles).toContain("var(--ac-surface)");
    expect(cardStyles).toContain("var(--ac-border-subtle)");
    expect(cardStyles).toContain("@media (prefers-reduced-motion: reduce)");
    expect(cardStyles).toContain("@media (forced-colors: active)");
    expect(cardStyles).not.toMatch(/var\(--(?:brand|gray|color)-/);
    expect(cardStyles).not.toContain("transform:");
  });
});
