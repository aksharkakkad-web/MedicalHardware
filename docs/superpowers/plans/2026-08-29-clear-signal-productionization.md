# Clear Signal Productionization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Clear Signal V3.0 the single, clinically honest, accessible design system used by the Adaptive Care clinic frontend and its `/design-system` reference page.

**Architecture:** Put canonical CSS tokens in one shared stylesheet, keep product semantics in typed React components, and make the reference page render the same components the clinic app can consume. Preserve the existing `MonitoringClient` boundary. Do not change backend contracts in this plan. Remove or label UI claims that the current frontend contract cannot represent.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, CSS Modules, Vitest, Testing Library, Playwright-compatible browser QA.

---

## File map

- `apps/clinic-dashboard/src/styles/design-tokens.css`: canonical Clear Signal V3.0 variables and temporary aliases.
- `apps/clinic-dashboard/src/app/globals.css`: imports shared tokens and keeps only global reset/application rules.
- `docs/design-system.md`: human and agent-readable Clear Signal rules, status semantics, migration, and governance.
- `apps/clinic-dashboard/src/app/design-system/page.tsx`: reference composition and operational examples.
- `apps/clinic-dashboard/src/app/design-system/page.module.css`: reference-page layout only, with no private token values.
- `apps/clinic-dashboard/src/app/design-system/design-system-shell.tsx`: section tracking, hash navigation, and focus movement.
- `apps/clinic-dashboard/src/components/app-shell/app-shell.tsx`: route-aware shell bypass for the reference route.
- `apps/clinic-dashboard/src/components/ui/*`: shared actions, fields, status indicators, attention item, and responsive records.
- `apps/clinic-dashboard/src/components/ui/*.test.tsx`: behavioral and semantic regression tests.

## Task 1: Canonical Clear Signal tokens and documentation

**Files:**
- Create: `apps/clinic-dashboard/src/styles/design-tokens.css`
- Modify: `apps/clinic-dashboard/src/app/globals.css`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.module.css`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.tsx`
- Modify: `docs/design-system.md`
- Create: `apps/clinic-dashboard/src/styles/design-tokens.test.ts`

- [ ] **Step 1: Add a failing token-consistency test**

The test reads the canonical stylesheet and checks the required roles, Clear Signal values, and absence of a second value-bearing `--signal-*` system in the page module.

```ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "../../..");
const tokens = readFileSync(resolve(root, "src/styles/design-tokens.css"), "utf8");
const pageCss = readFileSync(resolve(root, "src/app/design-system/page.module.css"), "utf8");

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
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `pnpm --dir apps/clinic-dashboard test -- src/styles/design-tokens.test.ts`

Expected: FAIL because the canonical stylesheet does not exist.

- [ ] **Step 3: Create canonical tokens and aliases**

Define `--ac-*` role, semantic, spacing, radius, shadow, motion, and typography values under `:root`. Map existing `--brand-*`, `--gray-*`, and `--color-*` names to the new roles so existing screens do not change in this task. Use dark navy for primary text, vivid blue for interaction, sky for informational accent, violet for brand accent only, mint for positive support, and green/amber/red/gray for operational state.

- [ ] **Step 4: Make the reference page consume `--ac-*` tokens**

Replace local value declarations with aliases such as:

```css
.viewport {
  --signal-canvas: var(--ac-canvas);
  --signal-surface: var(--ac-surface);
  --signal-text-primary: var(--ac-text-primary);
  --signal-action: var(--ac-action);
}
```

Aliases may remain during migration, but raw values live only in `design-tokens.css`.

- [ ] **Step 5: Rewrite the design-system document as Clear Signal V3.0**

Document one version, one token namespace, Geist Sans and Geist Mono, exact accent permissions, the six status axes, mobile record order, accessibility floor, and one-release legacy aliases. Remove Warm Indigo and Inter as active rules.

- [ ] **Step 6: Update visible version labels**

Use `ADAPTIVE CARE · DESIGN SYSTEM V3.0` in the masthead and `Clear Signal V3.0` in metadata. Remove “working system 02.”

- [ ] **Step 7: Verify Task 1**

Run:

```bash
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
git diff --check
```

Expected: 66 existing tests plus the token test pass, lint/typecheck/build exit 0, and existing clinic pages retain their current appearance.

## Task 2: Clinically honest terminology and six-axis status model

**Files:**
- Modify: `apps/clinic-dashboard/src/app/design-system/page.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/status-indicator.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/status-indicator.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/status-indicator.test.tsx`

- [ ] **Step 1: Add failing status-indicator tests**

```tsx
render(<StatusIndicator axis="freshness" value="stale" />);
expect(screen.getByText("Stale")).toBeVisible();
expect(screen.getByText(/last current update/i)).toBeVisible();

render(<StatusIndicator axis="monitoring" value="possible_multi_person" />);
expect(screen.getByText(/resident attribution unavailable/i)).toBeVisible();
```

Tests must also prove the API rejects a generic `tone` prop and requires an axis-specific value.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `pnpm --dir apps/clinic-dashboard test -- src/components/ui/status-indicator.test.tsx`

- [ ] **Step 3: Implement six typed axes**

```ts
type StatusProps =
  | { axis: "attention"; value: "critical" | "high" | "watch" | "none" }
  | { axis: "monitoring"; value: "active" | "away" | "possible_multi_person" | "paused" | "calibrating" | "unavailable" }
  | { axis: "confidence"; value: "high" | "medium" | "low" | "unavailable" }
  | { axis: "freshness"; value: "current" | "delayed" | "stale" | "unknown" }
  | { axis: "device"; value: "healthy" | "degraded" | "offline" | "maintenance" }
  | { axis: "workflow"; value: "new" | "acknowledged" | "investigating" | "resolved" };
```

Use “Monitoring current” rather than “Healthy” for overall availability. Use “High attention priority” rather than “High resident risk.” Keep device-health wording scoped to the device.

- [ ] **Step 4: Replace generic status specimens**

Show all six axes, their values, limitation copy, and one composite case. The composite must demonstrate that high attention, low confidence, offline device, and stale data can coexist without collapsing into one badge.

- [ ] **Step 5: Remove unsupported assignment claims**

Remove “Assign to me,” “Assign care owner,” and named ownership from canonical examples until the shared contract contains an assignee. Use supported workflow states instead.

- [ ] **Step 6: Add the evidence truth stack**

Add distinct sections for sensor evidence, deterministic warning, AI interpretation, and staff observation. AI copy must remain interpretation and cannot suppress deterministic warnings.

- [ ] **Step 7: Verify Task 2**

Run the focused test, full frontend test suite, lint, typecheck, build, and inspect the Status and Care Patterns sections at desktop and 390px.

## Task 3: Route semantics and accessibility

**Files:**
- Modify: `apps/clinic-dashboard/src/components/app-shell/app-shell.tsx`
- Modify: `apps/clinic-dashboard/src/components/app-shell/app-shell.test.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/design-system-shell.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.module.css`
- Create: `apps/clinic-dashboard/src/app/design-system/design-system-shell.test.tsx`

- [ ] **Step 1: Write failing tests for one main landmark and focus movement**

Test that `AppShell` returns children without clinic chrome on `/design-system`, ordinary routes retain the shell, and activating the skip link moves focus to `#design-system-content`.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `pnpm --dir apps/clinic-dashboard test -- src/components/app-shell/app-shell.test.tsx src/app/design-system/design-system-shell.test.tsx`

- [ ] **Step 3: Replace the DOM-ancestry hiding hack**

In `AppShell`, branch on `pathname.startsWith("/design-system")` and return children directly. Delete inert sibling manipulation from `DesignSystemShell`.

- [ ] **Step 4: Implement robust hash navigation**

Guard malformed hashes, listen for `hashchange` and `popstate`, update active state immediately on click, scroll the isolated root, and focus the destination with `tabIndex={-1}` and `{ preventScroll: true }`.

- [ ] **Step 5: Fix accessibility values**

Use navy text on Sky 400, raise primary and icon controls to at least 44px, label loading/success specimens as status examples rather than enabled action buttons, and make static examples clearly non-submitting.

- [ ] **Step 6: Verify Task 3**

Run focused and full tests, then inspect landmarks, keyboard order, skip navigation, section history, forced colors, reduced motion, and contrast.

## Task 4: Mobile resident records and navigation affordance

**Files:**
- Create: `apps/clinic-dashboard/src/components/ui/resident-records.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/resident-records.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/resident-records.test.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.module.css`
- Modify: `apps/clinic-dashboard/src/app/design-system/design-system-shell.tsx`

- [ ] **Step 1: Add failing responsive-record tests**

Tests must verify each record contains resident/room, attention reason, priority, confidence and freshness, workflow, and primary action in DOM order. Device details belong in a native `details` disclosure.

- [ ] **Step 2: Implement one data model and two presentations**

Use one typed `ResidentRecord` array. Render a semantic table at desktop and ordered record cards below 768px. Keep hover/selected as interaction examples separate from warning/critical product states.

- [ ] **Step 3: Add the mobile contents cue**

Show a right-edge fade and “More sections” affordance while horizontal contents remain. Hide the cue when scrolled to the end.

- [ ] **Step 4: Verify Task 4**

Run tests and inspect at 1440px, 768px, and 390px. No primary fact or action may require horizontal panning.

## Task 5: Shared product primitives

**Files:**
- Create: `apps/clinic-dashboard/src/components/ui/button.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/button.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/button.test.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/form-field.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/form-field.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/form-field.test.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/attention-item.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/attention-item.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/attention-item.test.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.tsx`

- [ ] **Step 1: Write failing behavior tests**

Cover button pending/disabled/accessible-name behavior, form label/hint/error relationships, and attention-item separation of attention, confidence, freshness, device, monitoring, workflow, and action.

- [ ] **Step 2: Implement minimal typed primitives**

Do not add a dependency. Use native button, input, textarea, select, fieldset, table, and details elements. Require explicit labels and status axes.

- [ ] **Step 3: Replace page-local specimens with shared components**

The design-system page must render the exported shared components. Delete equivalent duplicate page-only markup and CSS.

- [ ] **Step 4: Verify Task 5**

Run focused tests, full suite, lint, typecheck, build, and browser interaction checks.

## Task 6: Operational-state catalog

**Files:**
- Modify: `apps/clinic-dashboard/src/app/design-system/page.tsx`
- Modify: `apps/clinic-dashboard/src/app/design-system/page.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/system-state.tsx`
- Create: `apps/clinic-dashboard/src/components/ui/system-state.module.css`
- Create: `apps/clinic-dashboard/src/components/ui/system-state.test.tsx`

- [ ] **Step 1: Add failing state-catalog tests**

Verify the catalog includes calibrating, partial baseline, away/return, possible multi-person, device degraded/offline/buffering/retrying, missing assignment, unknown anomaly, AI pending/unavailable, loading, stale, save failure, conflict, overdue, resolved, and recurrence.

- [ ] **Step 2: Implement typed state examples**

Each state must name what is known, what is unavailable, why it matters, and the allowed next action. Label all examples synthetic or test-only where applicable.

- [ ] **Step 3: Add lifecycle and system feedback specimens**

Show open, acknowledged, investigating, overdue, resolved read-only, and recurrence as a new linked event. Add skeleton, empty, filtered empty, stale, retry, and conflict recovery.

- [ ] **Step 4: Verify Task 6**

Run tests and inspect long copy, keyboard behavior, forced colors, desktop, and mobile.

## Task 7: Final verification and PDF refresh

**Files:**
- Update: `output/pdf/adaptive-care-clear-signal-design-system.pdf`
- Update: `docs/superpowers/plans/2026-08-29-clear-signal-productionization.md`

- [ ] **Step 1: Run full fresh verification**

```bash
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
git diff --check
```

- [ ] **Step 2: Run browser QA**

Inspect `/design-system`, `/`, `/events`, and `/devices` at 1440px and 390px. Check console errors, keyboard path, focus, active navigation, 200% zoom, reduced motion, forced colors, overflow, and the main attention interaction.

- [ ] **Step 3: Run independent final reviews**

Dispatch one specification reviewer and one code-quality/accessibility reviewer. Resolve every P0/P1 finding and re-review.

- [ ] **Step 4: Export and inspect the PDF**

Export the complete long page with print backgrounds, render every PDF page to PNG, and inspect the first, middle, and last pages for clipped content, repeated app chrome, blank pages, or low-contrast text.

- [ ] **Step 5: Mark the plan complete**

Check every task box only after the corresponding fresh evidence exists. Do not push, open a PR, merge, or deploy without a separate user request and the repository delivery gate.
