import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesDirectory = import.meta.dirname;
const tokens = readFileSync(resolve(stylesDirectory, "design-tokens.css"), "utf8");
const pageCss = readFileSync(
  resolve(stylesDirectory, "../app/design-system/page.module.css"),
  "utf8",
);

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
});
