# Resident Context and Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mock-backed resident settings workspace for versioned context administration and future notification delivery choices.

**Architecture:** Extend the existing typed `MonitoringClient` boundary with resident-settings reads and commands. `MockMonitoringClient` owns fixture loading, expected-version validation, immutable history transitions, and browser persistence; React components consume only the client interface.

**Tech Stack:** Next.js App Router, React 19, TypeScript, CSS Modules, Vitest, Testing Library.

---

### Task 1: Typed resident-settings boundary

**Files:**
- Modify: `apps/clinic-dashboard/src/lib/monitoring/types.ts`
- Modify: `apps/clinic-dashboard/src/lib/monitoring/client.ts`
- Modify: `apps/clinic-dashboard/src/lib/monitoring/index.ts`
- Create: `apps/clinic-dashboard/src/mocks/resident-settings.ts`
- Modify: `apps/clinic-dashboard/src/mocks/mock-monitoring-client.ts`
- Test: `apps/clinic-dashboard/src/mocks/mock-monitoring-client.test.ts`

- [ ] Add contract-shaped preference, memory-entry, memory-response, and mutation-input types, including `expectedVersion` on every write.
- [ ] Add `getResidentSettings`, `updateNotificationPreferences`, `addMemoryEntry`, `correctMemoryEntry`, and `retireMemoryEntry` to `MonitoringClient`.
- [ ] Write client tests proving first save, normal save, stale rejection, add, correction linkage, retirement history, cloning, and storage persistence.
- [ ] Implement deterministic synthetic fixtures and the smallest mock transitions that make those tests pass. Corrections retire the selected entry and append one replacement; retirements never delete entries.
- [ ] Run `pnpm --dir apps/clinic-dashboard test` and expect all tests to pass.

### Task 2: Resident settings workspace

**Files:**
- Create: `apps/clinic-dashboard/src/app/residents/[residentId]/settings/page.tsx`
- Create: `apps/clinic-dashboard/src/features/resident-settings/resident-settings.tsx`
- Create: `apps/clinic-dashboard/src/features/resident-settings/resident-settings.module.css`
- Create: `apps/clinic-dashboard/src/features/resident-settings/resident-settings.test.tsx`
- Modify: `apps/clinic-dashboard/src/features/residents/resident-detail.tsx`
- Modify: `apps/clinic-dashboard/src/features/residents/resident-detail.module.css`
- Modify: `apps/clinic-dashboard/src/features/residents/resident-detail.test.tsx`

- [ ] Write component tests for loading success, add, correct, retire, first preference save, dashboard-visibility language, validation, and unavailable resident state.
- [ ] Build one combined workspace with a context ledger, add form, inline correction/retirement actions, and notification switches.
- [ ] Keep the audit trail visible, distinguish feedback from staff-added context, and state that delivery choices cannot hide high/critical dashboard events.
- [ ] Add a resident-detail link to `/residents/[residentId]/settings`.
- [ ] Run focused tests, then the full clinic test suite.

### Task 3: Browser finish and checkpoint

**Files:**
- Update generated graph files under `graphify-out/`.
- Capture screenshots under `.impeccable/review/` and the task visualization directory.

- [ ] Run the app and exercise add, correct, retire, and preference-save behavior in the browser.
- [ ] Inspect the normal desktop layout and 390px mobile layout together; check long copy, overflow, focus, disabled states, and console errors.
- [ ] Run the Impeccable detector once over changed TSX/CSS targets and fix mechanical findings in one batch.
- [ ] Run `pnpm --dir apps/clinic-dashboard test`, `lint`, `typecheck`, and `build`; expect zero failures.
- [ ] Run `graphify update .`, inspect the staged diff, and commit the completed checkpoint without pushing.
