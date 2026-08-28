# Clinic Dashboard Completion Plan

> Execute on the existing `cofounder/frontend-clinic-event-details` branch. The work is already isolated from `main`; creating another worktree would split one active feature across two locations.

## Task 1: Extend the frontend data boundary

**Files:** `src/lib/monitoring/client.ts`, `src/lib/monitoring/types.ts`, `src/mocks/mock-monitoring-client.ts`, related tests.

- Add typed event-list and resident-detail responses using existing domain objects.
- Make stored event progress visible in list responses.
- Add focused tests for list, resident lookup, not-found, and persistence behavior.
- Commit independently.

## Task 2: Build the shared shell and visual system

**Files:** `src/app/globals.css`, `src/components/app-shell/*`, new icon and shared presentation components.

- Replace placeholder navigation with real Overview and Events links.
- Use route-aware active states and a compact mobile navigation.
- Establish shared colors, typography, spacing, focus, surfaces, and status patterns.
- Keep the synthetic-data notice visible without dominating the interface.
- Update component tests and commit independently.

## Task 3: Build the event queue

**Files:** new `src/app/events/page.tsx`, `src/features/events/event-list*`, hooks and tests.

- Fetch events through `MonitoringClient`.
- Add search and status/priority filters.
- Present high/open work first and retain resolved history.
- Link rows to event detail and residents.
- Cover loading, error, and no-results states; commit independently.

## Task 4: Build resident detail

**Files:** new `src/app/residents/[residentId]/*`, `src/features/residents/resident-detail*`, hooks and tests.

- Show assignment, honest monitoring state, device status, and event history.
- Link active events into the workflow and provide a safe not-found state.
- Keep the screen responsive and accessible; commit independently.

## Task 5: Redesign existing screens

**Files:** overview and event-detail feature modules, CSS modules, and tests.

- Convert Overview into a calm operational summary plus a scan-friendly resident table.
- Restructure event detail into a readable header, evidence story, and sticky next-action panel.
- Preserve every working action, feedback, history, recurrence, uncertainty, and device state.
- Commit the overview and event-detail revisions in small reviewed parts.

## Task 6: Product and visual quality gate

- Run Impeccable's required detector exactly once on all changed visual targets.
- Run focused tests during development, then full test, lint, typecheck, and build.
- Start the real app and inspect desktop and mobile views plus the main event journey.
- Check keyboard focus, overflow, console errors, and reduced-motion behavior.
- Run `graphify update .`, review the complete diff, and ask one independent finish reviewer to inspect it.
- Fix all valid findings and rerun the entire verification set.

## Task 7: GitHub delivery

- Follow `github-delivery-gate` before any push.
- Push the branch, open a pull request, and run Greploop against the latest commit until Greptile reports 5/5 with zero unresolved actionable comments.
- Re-verify after every pushed fix.
- Squash merge into `main`, delete the source branch, update the local checkout, and leave the clinic app running on a clearly reported URL.
