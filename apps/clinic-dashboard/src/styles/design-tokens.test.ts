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
  // Brand scale
  "brand-50": "#eff6ff",
  "brand-100": "#dbeafe",
  "brand-200": "#bfdbfe",
  "brand-500": "#2f6fed",
  "brand-600": "#155eef",
  "brand-700": "#004eeb",
  "brand-800": "#00359e",
  // Gray scale
  "gray-0": "#ffffff",
  "gray-25": "#fcfcfd",
  "gray-50": "#f9fafb",
  "gray-75": "#f7f8fa",
  "gray-100": "#f2f4f7",
  "gray-200": "#e4e7ec",
  "gray-300": "#d0d5dd",
  "gray-400": "#98a2b3",
  "gray-500": "#667085",
  "gray-600": "#475467",
  "gray-700": "#344054",
  "gray-800": "#1d2939",
  "gray-900": "#171a21",
  // Operational status
  success: "#147d5a",
  "success-strong": "#10704f",
  "success-bg": "#ecfdf3",
  "success-border": "#abefc6",
  warning: "#a15c00",
  "warning-strong": "#854a00",
  "warning-bg": "#fffaeb",
  "warning-border": "#fedf89",
  danger: "#c4322b",
  "danger-strong": "#a82a24",
  "danger-bg": "#fef3f2",
  "danger-border": "#fecdca",
  "neutral-status": "#667085",
  "neutral-status-strong": "#475467",
  "neutral-status-bg": "#f2f4f7",
  "neutral-status-border": "#d0d5dd",
  // Layout roles
  background: "#f7f8fa",
  surface: "#ffffff",
  "surface-subtle": "#f9fafb",
  "text-primary": "#171a21",
  "text-secondary": "#667085",
  "text-tertiary": "#98a2b3",
  border: "#e4e7ec",
  "border-strong": "#d0d5dd",
  primary: "#155eef",
  "primary-hover": "#004eeb",
  "primary-subtle": "#eff6ff",
  // Legacy color roles
  "color-canvas": "#f7f6f2",
  "color-text": "#1d1d1f",
  "color-surface": "#ffffff",
  "color-text-muted": "#636366",
  "color-text-soft": "#6e6e73",
  "color-border": "#dedee3",
  "color-accent-strong": "#075bd8",
  "color-accent-soft": "#edf4ff",
  "color-accent-soft-hover": "#e2edff",
  "color-accent-border": "#c9dcfb",
  "color-status-neutral-text": "#52605b",
  "color-status-neutral-bg": "#f2f4f3",
  "color-status-healthy-text": "#12604d",
  "color-status-healthy-bg": "#e4f3ed",
  "color-status-attention-text": "#875006",
  "color-status-attention-bg": "#fff2d9",
  "color-status-critical-text": "#9f2d25",
  "color-status-critical-bg": "#ffebe8",
  "color-status-unavailable-text": "#59635f",
  "color-status-unavailable-bg": "#ecefed",
  // Geometry and spacing
  "radius-xs": "4px",
  "radius-sm": "6px",
  "radius-md": "8px",
  "radius-lg": "12px",
  "radius-pill": "999px",
  "radius-control": "0.75rem",
  "radius-card": "1rem",
  "space-1": "4px",
  "space-2": "8px",
  "space-3": "12px",
  "space-4": "16px",
  "space-6": "24px",
  "space-8": "32px",
  "space-12": "48px",
  "space-16": "64px",
  // Layout dimensions
  "sidebar-width": "240px",
  "topbar-height": "64px",
  "page-padding": "32px",
  // Motion and elevation
  "duration-fast": "150ms",
  "duration-medium": "180ms",
  "duration-slow": "200ms",
  "shadow-card": "0 1px 2px rgb(16 24 40 / 4%)",
  "shadow-popover": "0 4px 8px -2px rgb(16 24 40 / 8%), 0 2px 4px -2px rgb(16 24 40 / 5%)",
  "shadow-dialog": "0 16px 32px -8px rgb(16 24 40 / 14%), 0 4px 8px -2px rgb(16 24 40 / 6%)",
  "focus-ring": "0 0 0 3px rgb(7 91 216 / 22%)",
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
    expect(Object.keys(compatibilityMappings)).toHaveLength(92);

    for (const [name, value] of Object.entries(compatibilityMappings)) {
      expect(tokens).toContain(`--ac-legacy-${name}: ${value}`);
      expect(tokens).toContain(`--${name}: var(--ac-legacy-${name})`);
    }
  });
});
