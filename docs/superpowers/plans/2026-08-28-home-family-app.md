# Home and Family App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a separate mock-backed home application with a loved-one overview, family-safe update detail and feedback, and versioned routine input.

**Architecture:** Bootstrap `apps/home-app` as an independent Next.js application. Components depend on a typed `HomeMonitoringClient`; a persistent `MockHomeMonitoringClient` supplies synthetic domain responses and local write behavior. The app does not import clinic UI or expose clinic operations.

**Tech Stack:** Next.js 16, React 19, TypeScript, CSS Modules, Vitest, Testing Library, localStorage.

---

### Task 1: App bootstrap and typed client

**Files:**
- Create: `apps/home-app/package.json`
- Create: `apps/home-app/tsconfig.json`
- Create: `apps/home-app/next.config.ts`
- Create: `apps/home-app/eslint.config.mjs`
- Create: `apps/home-app/vitest.config.ts`
- Create: `apps/home-app/src/test/setup.ts`
- Create: `apps/home-app/src/lib/home-monitoring/types.ts`
- Create: `apps/home-app/src/lib/home-monitoring/client.ts`
- Create: `apps/home-app/src/lib/home-monitoring/provider.tsx`
- Create: `apps/home-app/src/lib/home-monitoring/index.ts`

- [ ] Write a test file for the mock client imports before implementation; run it and confirm the missing-module failure.
- [ ] Define family-safe overview, trend, update, feedback, and routine types with schema version `1.0`.
- [ ] Define the six-method `HomeMonitoringClient` interface from the approved design.
- [ ] Add a client provider and hook that throw a clear developer error when missing.
- [ ] Add the Next.js/Vitest/ESLint configuration and install dependencies with `pnpm install`.
- [ ] Run `pnpm --dir apps/home-app typecheck` and fix configuration errors.
- [ ] Commit with `feat: bootstrap home monitoring client`.

### Task 2: Persistent mock family data

**Files:**
- Create: `apps/home-app/src/mocks/home-fixtures.ts`
- Create: `apps/home-app/src/mocks/mock-home-monitoring-client.ts`
- Create: `apps/home-app/src/mocks/mock-home-monitoring-client.test.ts`

- [ ] Write failing tests for overview cloning, family-safe update detail, feedback validation/persistence, routine add/retire/version checks, and malformed-storage fallback.
- [ ] Run `pnpm --dir apps/home-app test -- mock-home-monitoring-client.test.ts` and confirm red.
- [ ] Build synthetic fixtures using only plain family language and explicit uncertainty.
- [ ] Implement the mock client with separate feedback and routine storage keys, structured cloning, expected-version checks, and safe storage failure handling.
- [ ] Run the focused tests and confirm green.
- [ ] Commit with `feat: add home app mock data client`.

### Task 3: Shared home shell and Today screen

**Files:**
- Create: `apps/home-app/src/app/layout.tsx`
- Create: `apps/home-app/src/app/providers.tsx`
- Create: `apps/home-app/src/app/globals.css`
- Create: `apps/home-app/src/app/page.tsx`
- Create: `apps/home-app/src/components/home-shell/home-shell.tsx`
- Create: `apps/home-app/src/components/home-shell/home-shell.module.css`
- Create: `apps/home-app/src/components/icons.tsx`
- Create: `apps/home-app/src/features/today/today.tsx`
- Create: `apps/home-app/src/features/today/today.module.css`
- Create: `apps/home-app/src/features/today/today.test.tsx`

- [ ] Write failing tests for the steady answer, limitation note, three trends, important update link, routines link, loading, and error states.
- [ ] Run the focused test and confirm red.
- [ ] Build the responsive Morning Window shell with Today, Updates, and Routines navigation.
- [ ] Build the status window, continuous trend sheet, important update record, and recent activity.
- [ ] Run the focused tests, lint, and typecheck.
- [ ] Commit with `feat: add home today experience`.

### Task 4: Update detail and family feedback

**Files:**
- Create: `apps/home-app/src/app/updates/[eventId]/page.tsx`
- Create: `apps/home-app/src/features/updates/update-detail.tsx`
- Create: `apps/home-app/src/features/updates/update-detail.module.css`
- Create: `apps/home-app/src/features/updates/update-detail.test.tsx`

- [ ] Write failing tests for family-safe evidence, uncertainty, no clinic controls, feedback choices, validation, saved summary, loading, missing, and error states.
- [ ] Run the focused test and confirm red.
- [ ] Build the explanation sheet and simple feedback form with native radio controls and live save feedback.
- [ ] Confirm the saved view is read-only and survives mock-client recreation.
- [ ] Run focused tests, lint, and typecheck.
- [ ] Commit with `feat: add family update feedback`.

### Task 5: Routine and context screen

**Files:**
- Create: `apps/home-app/src/app/routines/page.tsx`
- Create: `apps/home-app/src/features/routines/routines.tsx`
- Create: `apps/home-app/src/features/routines/routines.module.css`
- Create: `apps/home-app/src/features/routines/routines.test.tsx`

- [ ] Write failing tests for active/retired history, add, trim/validation, retire reason, version conflict, loading, and error states.
- [ ] Run the focused test and confirm red.
- [ ] Build the one-sentence input, active routine list, retire flow, and preserved history.
- [ ] Run focused tests, lint, and typecheck.
- [ ] Commit with `feat: add family routine workspace`.

### Task 6: Whole-app verification

**Files:**
- Update: `apps/home-app/DESIGN.md` only if the implementation introduces a durable approved pattern.
- Update: `graphify-out/`

- [ ] Run `pnpm --dir apps/home-app test`, `lint`, `typecheck`, and `build`.
- [ ] Run the Impeccable detector once over all new TSX and CSS targets.
- [ ] Start the app on port 3200 and verify Today → update feedback and Today → routine add/retire at 1440px and 390px.
- [ ] Inspect loading/error/long text, keyboard focus, overflow, and console errors.
- [ ] Apply one bounded visual-fix batch and reconfirm once.
- [ ] Run an independent read-only finish review and resolve material findings.
- [ ] Run `graphify update .`, stage exact paths, inspect the staged diff, and commit verification/documentation changes.
