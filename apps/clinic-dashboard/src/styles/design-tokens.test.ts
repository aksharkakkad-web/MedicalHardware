import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesDirectory = import.meta.dirname;
const tokens = readFileSync(resolve(stylesDirectory, "design-tokens.css"), "utf8");
const pageCss = readFileSync(
  resolve(stylesDirectory, "../app/design-system/page.module.css"),
  "utf8",
);

const compatibilityMappings = {
  "brand-500": "#2f6fed",
  "brand-800": "#00359e",
  "gray-25": "#fcfcfd",
  "gray-600": "#475467",
  "gray-900": "#171a21",
  background: "#f7f8fa",
  surface: "#ffffff",
  "surface-subtle": "#f9fafb",
  "text-primary": "#171a21",
  "text-secondary": "#667085",
  border: "#e4e7ec",
  primary: "#155eef",
  success: "#147d5a",
  "success-bg": "#ecfdf3",
  warning: "#a15c00",
  "warning-border": "#fedf89",
  danger: "#c4322b",
  "danger-strong": "#a82a24",
  "neutral-status": "#667085",
  "color-canvas": "#f7f6f2",
  "color-text": "#1d1d1f",
  "color-accent-strong": "#075bd8",
  "color-status-healthy-text": "#12604d",
  "color-status-critical-bg": "#ffebe8",
  "radius-control": "0.75rem",
  "radius-card": "1rem",
  "radius-md": "8px",
  "space-4": "16px",
  "space-16": "64px",
  "shadow-card": "0 1px 2px rgb(16 24 40 / 4%)",
  "shadow-dialog": "0 16px 32px -8px rgb(16 24 40 / 14%), 0 4px 8px -2px rgb(16 24 40 / 6%)",
  "sidebar-width": "240px",
  "topbar-height": "64px",
  "page-padding": "32px",
  "duration-fast": "150ms",
  "duration-slow": "200ms",
} as const;

describe("Clear Signal tokens", () => {
  it("defines the canonical product roles", () => {
    expect(tokens).toContain("--ac-canvas: #fbfaf8");
    expect(tokens).toContain("--ac-surface: #ffffff");
    expect(tokens).toContain("--ac-text-primary: #111827");
    expect(tokens).toContain("--ac-action: #175cd3");
    expect(tokens).toContain("--ac-info-accent: #55acff");
    expect(tokens).toContain("--ac-brand-accent: #7357d8");
    expect(tokens).toContain("--ac-positive-accent: #76d6b1");
  });

  it("keeps token values out of the reference-page module", () => {
    expect(pageCss).not.toMatch(/--signal-[\w-]+\s*:\s*#/);
  });

  it("keeps legacy aliases on the frozen compatibility tier", () => {
    for (const [name, value] of Object.entries(compatibilityMappings)) {
      expect(tokens).toContain(`--ac-legacy-${name}: ${value}`);
      expect(tokens).toContain(`--${name}: var(--ac-legacy-${name})`);
    }
  });
});
