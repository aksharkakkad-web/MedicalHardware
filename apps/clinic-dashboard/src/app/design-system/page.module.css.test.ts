import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(resolve(process.cwd(), "src/app/design-system/page.module.css"), "utf8");
const printRules = stylesheet.slice(stylesheet.lastIndexOf("@media print"));

describe("design-system print stylesheet", () => {
  it("turns the internal viewport back into printable document flow", () => {
    expect(printRules).toMatch(/\.viewport\s*\{[\s\S]*position:\s*static;/);
    expect(printRules).toMatch(/\.viewport\s*\{[\s\S]*width:\s*auto;/);
    expect(printRules).toMatch(/\.viewport\s*\{[\s\S]*height:\s*auto;/);
    expect(printRules).toMatch(/\.viewport\s*\{[\s\S]*overflow-y:\s*visible;/);
    expect(printRules).toMatch(/\.viewport\s*\{[\s\S]*scroll-snap-type:\s*none;/);
    expect(printRules).toMatch(/\.skipLink,[\s\S]*\.index,[\s\S]*display:\s*none\s*!important;/);
    expect(printRules).toMatch(/\.section\s*\{[\s\S]*break-inside:\s*auto;/);
    expect(printRules).toMatch(/\.section\s*\{[\s\S]*border-bottom:\s*0;[\s\S]*background:\s*transparent;/);
    expect(printRules).toMatch(/\.section \+ \.section\s*\{[\s\S]*break-before:\s*page;/);
    expect(printRules).toMatch(/\.section:nth-of-type\(odd\)\s*\{[\s\S]*background:\s*transparent;/);
    expect(printRules).toMatch(/\.pageFooter\s*\{[\s\S]*display:\s*none;/);
    expect(printRules).toMatch(/\.section:last-of-type \.sectionBody\s*\{[\s\S]*padding-bottom:\s*0;/);
  });

  it("protects specimen units and preserves the content surface for print", () => {
    expect(printRules).toMatch(/\.swatchStrip > div,[\s\S]*\.statusAxisCard,[\s\S]*break-inside:\s*avoid;/);
    expect(printRules).toMatch(/\.content \[data-attention-item\],[\s\S]*\.content \[data-system-state\],[\s\S]*break-inside:\s*avoid;/);
    expect(printRules).toMatch(/\.content \*\s*\{[\s\S]*animation:\s*none\s*!important;[\s\S]*transition:\s*none\s*!important;/);
    expect(printRules).toMatch(/\.content a::after\s*\{[\s\S]*content:\s*none\s*!important;/);
    expect(printRules).not.toMatch(/\.(?:content|section|sectionBody|hero)\s*\{[^}]*display:\s*none/);
    expect(printRules).not.toMatch(/\.viewport\s*\{[^}]*overflow(?:-y)?\s*:\s*(?:hidden|clip)/);
  });
});
