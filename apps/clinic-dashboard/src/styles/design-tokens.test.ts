import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesDirectory = import.meta.dirname;
const tokens = readFileSync(resolve(stylesDirectory, "design-tokens.css"), "utf8");
const pageCss = readFileSync(resolve(stylesDirectory, "../app/design-system/page.module.css"), "utf8");

describe("Care Ledger tokens", () => {
  it("defines the restrained Dub-derived product foundation", () => {
    expect(tokens).toContain("--ac-canvas: #ffffff");
    expect(tokens).toContain("--ac-surface: #ffffff");
    expect(tokens).toContain("--ac-surface-quiet: #f5f5f5");
    expect(tokens).toContain("--ac-text-primary: #171717");
    expect(tokens).toContain("--ac-text-secondary: #737373");
    expect(tokens).toContain("--ac-border-subtle: #e5e5e5");
    expect(tokens).toContain("--ac-action: #2563eb");
    expect(tokens).toContain("--ac-radius-input: 6px");
    expect(tokens).toContain("--ac-radius-control: 8px");
    expect(tokens).toContain("--ac-radius-card: 12px");
    expect(tokens).toContain("--ac-shadow-card: none");
  });

  it("locks the compact shell and working-surface dimensions", () => {
    expect(tokens).toContain("--ac-sidebar-width: 208px");
    expect(tokens).toContain("--ac-sidebar-collapsed-width: 58px");
    expect(tokens).toContain("--ac-topbar-height: 56px");
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
