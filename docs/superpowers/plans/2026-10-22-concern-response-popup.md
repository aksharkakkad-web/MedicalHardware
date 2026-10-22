# Concern response popup implementation plan

> Agentic implementation: use the current-session subagent workflow for the independent modal primitive; root owns feature integration and verification.

**Goal:** Open response and explicit resolution quickly from concern queues and detail, with an accessible popup and unchanged lifecycle rules.

**Architecture:** Extract existing EventActions/ResolutionForm into a reusable feature module. A page-owned response-dialog hook selects an event by ID and renders outside filtered rows, so successful resolution can remove a row without destroying completion feedback. A native dialog primitive handles top-layer presentation, keyboard dismissal, focus restoration and scroll containment. ConcernRow receives a callback; its button is a sibling of the record link, avoiding nested controls and circular imports.

**Stack:** Next.js/React/TypeScript, CSS modules, native HTML dialog, Vitest/Testing Library.

## Reuse report

Requested capability: easy popup access to existing response/outcome and resolution. Existing matches: EventActions, ResolutionForm, typed WorkspaceClient, permissions, retry identities and errors in care-event-detail.tsx. Docs: V6 design tokens and the functional PRD already define state and authorization semantics. History: PR21/fc13b28 owns workflows; PR23/4ff7d90 completion; PR24/906fe19 presentation. Only backend PR20 remains open with no apps overlap. Verdict: extend. There is no existing modal implementation. No backend/shared schema changes are required.

## Task 1 — Accessible modal primitive

Files: create components/ui/modal.tsx, modal.module.css, modal.test.tsx; minimally extend src/test/setup.ts with native-dialog test shims. API: Modal({open, title, description?, children, onRequestClose, dismissDisabled?}). Use generated title IDs, title focus, native showModal/close, controlled Escape, a visible Close button, existing overlay/dialog tokens, bounded scrollable content and prior focus restoration (main workspace fallback if trigger disappeared). Preserve previous body scroll styles. Closing must not invoke an action. Do not implement a custom focus trap where the browser already provides one.

- [x] Write and observe failing tests for opening/labeling, Close/Escape, blocked dismissal and focus restoration.
- [x] Implement the primitive and verify its tests. Native focus containment also requires browser verification.

## Task 2 — Shared feature popup

Files: create features/workspace/care-response-actions.tsx and care-response-dialog.tsx; modify care-event-detail.tsx, care-shared.tsx, care-overview.tsx, care-resident-detail.tsx, care-handover.tsx and care-workspace.module.css.

- [x] Add failing tests: queue Respond opens the correct event without navigation; detail opens the same popup; closing does not mutate; resolved rows have no Respond control; actual dirty entry requires explicit discard; pending save cannot dismiss.
- [x] Extract the existing handlers without changing client calls, request IDs, validation or eligibility. Keep a completed canonical check valid even without local check metadata. No high/critical urgency is downgraded by UI code.
- [x] Add response/resolution choices to the popup. Resolution remains gated by completed check, no outstanding event follow-up and the existing permission. Remove the buried nested resolution accordion. Display the reason when resolution is unavailable. Preserve errors/entries on failed saves. Keep current event identity/room/resident/status/limitations visible.
- [x] Add page-owned useConcernResponseDialog(), returning openResponse(eventId, mode?) and responseDialog. Render it outside all event maps. Add a sibling Respond button to open concern rows in overview/events/resident/handover and a prominent detail trigger. Replace the duplicate inline form with a compact launcher. Preserve full record navigation.
- [x] Keep the popup open on success, showing completed green state. If its trigger is removed, restore focus to the main workspace. Read current authorized snapshots by event ID; unavailable/revoked scope cannot retain actionable data. Prevent dismissal during saves; actual dirty fields show Keep editing/Discard and close.
- [x] Update workflow tests to open the popup before interacting. Exercise the same real DemoWorkspaceClient lifecycle, failure/retry and permissions paths.

## Task 3 — Verify and deliver

- [x] Run clinic tests, lint, typecheck and optimized build. Review integration and import boundaries.
- [x] Inspect list, detail, checked/resolved, view-only, keyboard Escape/Tab and focus return, and phone popup scroll/controls. Use isolated localhost synthetic state for care actions; preserve the user's 127.0.0.1 journal.
- [x] Update the design guide/download/reference and implementation record to describe the new interaction accurately.
- [ ] Create a PR, attach it, run repository CI, request configured review and merge under standing authorization. Record any unavailable automated review accurately; preserve hardware checkout/backend PR20.

## Verification record

266 clinic tests pass; lint, typecheck and optimized build pass. The design-reference tests also pass after the documentation note. Source review found and verified fixes for discard/pending bypass and resolution draft loss when eligibility changes. Desktop/phone browser checks confirm real native modal behavior, dirty-close protection, separate check/resolution, green confirmation after queue removal and main focus fallback. Graphify update was attempted but the executable is unavailable. Delivery/CI/review/merge evidence is tracked in the associated PR; no missing Greptile score is asserted as a pass.
