# SYREN native care interface redesign

> **For agentic workers:** Use subagent-driven-development with disjoint visual ownership. Preserve the client boundary and all existing care workflows.

**Goal:** Replace the flat ledger presentation with a polished Apple-inspired care workspace with purposeful color, depth and hierarchy.

**Architecture:** Extend the current tokens, shell, primitives and shared care/admin surfaces. No backend, state-model, permission, API or hardware changes. Existing response and assignment handlers remain authoritative.

**Tech stack:** Next.js, React, TypeScript, CSS Modules, Vitest.

## Reuse report

- Requested capability: visual redesign of the existing clinic app.
- Current implementation matches: AppShell, shared UI primitives, care-shared.tsx, care-workspace.module.css and workspace-admin.module.css already centralize the applicable presentation.
- Documentation matches: docs/design-system.md V3 specifies the current neutral ledger; revise it in this change to match the user's newly requested direction.
- History matches: fc13b28 / PR21 delivered the shared workflows; 5b9c628 / PR18 supplied the former Dub foundation. Reuse working behavior.
- Remote matches: PR20 is backend-only; no open frontend PR overlaps this work.
- Verdict: extend.
- Boundary: clinic presentation and visual documentation only. No data-contract edits.
- Evidence gaps: Graphify executable unavailable; existing graph omits the current care components. Live source inspection used.

## Visual direction

Use native system type, a cool gray canvas, white grouped content panels, subtle surface shadows, translucent navigation chrome, clear blue interaction and selective colored status anchors. Color always accompanies text. Keep attention above the roster, preserve uncertainty and timestamps, and keep phone response controls reachable. No invented values, decorative charts, marketing hero, random avatars or repeated generic cards.

Apple references: https://developer.apple.com/design/human-interface-guidelines/color and https://developer.apple.com/design/human-interface-guidelines/materials. Adapt the principles to the web; do not claim this implements a native Apple material or SDK component.

## Implementation

- [x] Foundation and shell: update design-tokens.css, app-shell styles/markup and shared input/button/status primitives. Use system fonts without downloading Apple fonts. Retain all navigation, demo labels and access controls.
- [x] Care: update shared concern rows, overview/roster and detail panels. Retain action labels, real links, source dates, quality states and all permission checks.
- [x] Administration: turn flat section dividers into native-settings-style grouped sections, preserve form structure and confirmation/retry states.
- [x] Documentation: update docs/design-system.md, downloadable guide and the design-system route's visible version/narrative.
- [x] Verify: run clinic tests, lint, typecheck and build; inspect desktop, tablet and phone. Check overflow, focus, accessible contrast and core filter/response/admin flows. Fix actual regressions.
Delivery evidence is recorded in the associated GitHub PR: current review result, CI and merge state. The revised preview remains available locally. No unavailable review score is assumed.

## Acceptance

The first viewport must visibly differ from V3 through surface separation, typography, navigation treatment and semantic color. All existing operational workflows and truthful demo boundaries remain intact. No product behavior may depend on new decoration. Desktop and phone must remain readable without horizontal page overflow.

Canonical checks:

```bash
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
```
