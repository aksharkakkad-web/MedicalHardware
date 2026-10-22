import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesDirectory = import.meta.dirname;
const tokens = readFileSync(resolve(stylesDirectory, "design-tokens.css"), "utf8");
const pageCss = readFileSync(resolve(stylesDirectory, "../app/design-system/page.module.css"), "utf8");

describe("SYREN native care tokens", () => {
  it("defines distinct native-inspired canvas and working surfaces", () => {
    expect(tokens).toContain("--ac-canvas: #f4f7f8");
    expect(tokens).toContain("--ac-surface: #ffffff");
    expect(tokens).toContain("--ac-surface-quiet: #eef4f5");
    expect(tokens).toContain("--ac-text-primary: #19333f");
    expect(tokens).toContain("--ac-text-secondary: #586b74");
    expect(tokens).toContain("--ac-border-subtle: #dce5e9");
    expect(tokens).toContain("--ac-action: #086b83");
    expect(tokens).toContain("--ac-radius-input: 8px");
    expect(tokens).toContain("--ac-radius-control: 8px");
    expect(tokens).toContain("--ac-radius-card: 12px");
    expect(tokens).toContain("--ac-shadow-card: none");
  });

  it("keeps body, action and semantic text readable on their intended surfaces", () => {
    function color(role: string) {
      const value = tokens.match(new RegExp(`--ac-${role}: (#[0-9a-f]{6});`))?.[1];
      if (!value) throw new Error(`Missing color role ${role}`);
      return value;
    }
    function luminance(hex: string) {
      const channels = [1, 3, 5].map((i) => {
        const component = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
        return component <= 0.04045 ? component / 12.92 : ((component + 0.055) / 1.055) ** 2.4;
      });
      return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
    }
    for (const [text, background] of [
      ["text-primary", "canvas"], ["text-secondary", "canvas"],
      ["text-secondary", "surface"], ["action", "surface"],
      ["text-inverse", "action"], ["risk-text", "risk-bg"],
      ["watch-text", "watch-bg"], ["positive-text", "positive-bg"],
      ["navigation-text", "navigation-bg"],
      ["navigation-muted", "navigation-bg"],
      ["navigation-active-text", "navigation-active-bg"],
      ["text-inverse", "info-accent"],
      ["text-inverse", "positive-accent"],
    ]) {
      const a = luminance(color(text));
      const b = luminance(color(background));
      expect((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05), `${text} on ${background}`).toBeGreaterThanOrEqual(4.5);
    }
    const boundary = luminance(color("border-control"));
    const surface = luminance(color("surface"));
    expect((surface + 0.05) / (boundary + 0.05), "enabled control boundary on white").toBeGreaterThanOrEqual(3);
  });

  it("locks the compact shell and working-surface dimensions", () => {
    expect(tokens).toContain("--ac-sidebar-width: 232px");
    expect(tokens).toContain("--ac-sidebar-collapsed-width: 72px");
    expect(tokens).toContain("--ac-topbar-height: 68px");
    expect(tokens).toContain("--ac-page-gutter: 32px");
    expect(tokens).toContain("--ac-secondary-rail-width: 320px");
    expect(tokens).toContain("--ac-detail-sheet-width: 400px");
    expect(tokens).toContain("--ac-dialog-width: 480px");
  });

  it("keeps compatibility roles mapped to the canonical ac namespace", () => {
    for (const role of [
      "--color-canvas: var(--ac-canvas)",
      "--color-surface: var(--ac-surface)",
      "--color-text: var(--ac-text-primary)",
      "--color-border: var(--ac-border-subtle)",
      "--color-accent-strong: var(--ac-action)",
      "--signal-action: var(--ac-action)",
      "--signal-radius-card: var(--ac-radius-card)",
    ]) expect(tokens).toContain(role);
  });

  it("keeps value-bearing color decisions out of the reference-page module", () => {
    expect(pageCss).not.toMatch(/--signal-[\w-]+\s*:\s*#/);
  });
});
