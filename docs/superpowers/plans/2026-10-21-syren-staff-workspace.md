# SYREN Staff Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace obsolete clinic presentation with a polished, accessible SYREN facility workspace implementing the October 21 functional PRD, verify it in a browser, and merge through a reviewed PR.

**Architecture:** Extend the existing typed MonitoringClient, provider, event behavior and mock infrastructure. A frontend workspace service composes that monitoring client with facility/shared-client/quick-check/follow-up/import metadata; production-only capabilities remain explicitly unavailable until authorized backend APIs exist. UI-first production components consume providers, never fixtures or database internals.

**Tech Stack:** Next.js 16, React 19, TypeScript, CSS modules and existing Care Ledger tokens, Vitest and Testing Library.

## Authorization and reuse report

The founder authorized autonomous design and implementation, removal of obsolete clinic frontend material, no routine questions, and squash merging the completed change. Aesthetic quality and avoidance of generic generated dashboard patterns are primary acceptance criteria. The three-hour absence is an expected work window, not an unsupported automatic runtime guarantee.

Requested capability: complete self-contained care-facility frontend with area-scoped shared clients, actionable concerns, resident records/readings, quick checks, follow-up, handover, facility administration and private import review.

Current implementation matches: apps/clinic-dashboard already contains MonitoringClient, provider, resident/event/device/settings features, contract-valid mocks and 25 test files. src/app/providers.tsx currently always constructs MockMonitoringClient. There is no production station authentication or independent notification delivery.

Contract/documentation matches: docs/PRD.md, ARCHITECTURE.md, DATA_CONTRACT.md and BUILD_PLAN.md explicitly prescribe production UI built against mock clients, then real API integration. The October 21 frontend functional PRD adds required shared-client and care workflows. Existing event statuses and server semantics remain authoritative.

History matches: merged frontend PRs #6, #12, #15, #16 and #18. Fresh live main b6acc17f4b829c7c83953ea27a108b78e073c495 adds hardware assets after #18 without changing clinic source.

Issue/PR matches: no frontend PR or issues found; PR20 remains open at 2b6f305d100af6fbebc92a6700f2cd6b081a7f0b and owns backend intelligence/ingestion and shared OpenAPI changes.

Verdict: EXTEND reusable interfaces and tested behaviors; REPLACE obsolete product presentation and unused starter material; COORDINATE backend-owned capabilities through an explicit dependency audit without duplicating PR20.

Recommended implementation boundary: apps/clinic-dashboard plus this task's frontend documentation. Preserve apps/home-app, backend, firmware and the dirty primary hardware checkout. Root agent is sole editor of shared docs and the workspace integration contract.

Evidence gaps: main has no production auth, measurement/trends endpoints, private import processing or independent notification delivery. Keep demo data unmistakably synthetic, never fabricate real support. Greptile's trial was reported expired on PR20; attempt prescribed review on the new PR and report the actual result without weakening branch protections.

## Visual and operational contract

Use the existing neutral tokens and Geist typography as a restrained foundation. Build a deliberately composed staff workspace with clear room identity, priority, current work and resident context. No decorative gradients, glass, oversized landing-page heroes, KPI-card wall, gratuitous avatars, fake trend statistics, all-purpose pill badges or empty feature cards. One consistent shell, natural language, fine rules, measured spacing and usable mobile layouts. Prioritize the action queue and area roster in one initial workspace.

A current reading never proves safety. Missing, stale, away and multi-person states remain distinct. Acknowledgment does not prove physical response or a check. Quick outcomes cannot accidentally mark an unsuccessful check complete. Resolved history stays immutable. Shared actions identify the client, not a nurse. Real notification/authentication/storage delivery must not be simulated as production success.

## Task 1 Workspace data composition

Files: create src/lib/workspace/{types,client,provider,demo-client,index}.ts or .tsx and tests; adapt existing mock/core only where explicitly needed.

- [x] Define and publish a compact frontend-only workspace interface before consumers begin. Core resident/event objects use the existing MonitoringClient types; avoid another competing event engine.
- [x] Write failing behavior tests for scope filtering, area selection, unable-to-check semantics, unresolved follow-up, duplicate actions, preserved history, and demo persistence/reconciliation.
- [x] Implement the demo workspace service by composing the existing MonitoringClient. It supplies clearly synthetic measurements and dated resident context. It never rewrites unavailable states with fake readings.
- [x] Expose provider hooks for snapshot, loading/error, actions and refresh. Share contract with page implementers.
- [x] Keep external/backend capabilities explicit; evaluate an HTTP MonitoringClient against the actual Product API without treating development headers as production access. Production integration is deferred because the required workspace services/grants are absent.
- [x] Run focused tests and publish actual method signatures.

Core behavior assertion:
```ts
await client.recordCheck(eventId, { outcome: "unable_to_check", note: "" });
expect((await client.snapshot()).events.find(e => e.eventId === eventId)?.status).not.toBe("checked");
```

## Task 2 Main staff and resident experience

Files: create/replace features/workspace care overview, resident detail, event response/detail, and handover modules with route entry points; own their CSS modules and tests. Do not edit workspace service or root shell.

- [x] Write failing tests for area roster and actionable concerns, search, unavailable readings, and quick-check outcomes.
- [x] Build the combined area overview using real provider records, functional search/filter, response status and operational gaps.
- [x] Build resident detail with current readings, honest trend gaps, dated context, relevant concerns/history and follow-up.
- [x] Build event detail and quick response forms with meaningful outcome choices, optional notes, real save state and explicit resolution.
- [x] Build shift handover from unresolved work, follow-ups and monitoring gaps; preserve event identity.
- [x] Verify meaningful behavior and loading/empty/error states using Testing Library.

## Task 3 Facility and shared-client administration

Files: create features/workspace-admin modules and their route entry points/tests/CSS. Do not edit root shell or workspace service.

- [x] Write failing tests for facility setup, approved area/client, admin logout preserving routine use, and CSV import preview conflict handling.
- [x] Build facility details, areas and shared client approval/revocation using provider methods. Make simulated administration unmistakable in demo mode.
- [x] Add resident/directory input and import preview/apply with invalid rows and duplicate conflicts visible. Support actually implemented formats; do not fake PDF/XLSX extraction.
- [x] Expose sourced manual context and private-document review dependencies, plus notification-readiness/test prerequisites, honestly distinguishing missing backend support.
- [x] Show optional layout capability as unavailable until documented server support exists; the directory remains sufficient.
- [x] Run focused tests, report unavailable server capabilities clearly.

## Task 4 Shell visual integration and cleanup

Files: components/app-shell, app/layout.tsx, app/providers.tsx, app/globals.css, styles/design-tokens.css only if necessary, app routes, docs/design-system.md and clinic README. Root owns this task.

- [x] Preserve a baseline screenshot and passing baseline checks.
- [x] Integrate a cohesive SYREN shell, area context, demo/live mode explanation, navigation and administration entry.
- [x] Compose new screens with existing primitives and refine spacing/typography from rendered evidence.
- [x] Remove unreferenced starter page.module.css and next.svg/vercel.svg after reference checks; retire obsolete navigation and branding. Keep historical planning evidence and valid tests.
- [x] Keep Scenario Lab available only as a deliberate demo/development tool.
- [x] Update design-system documentation to match actual implementation and source-of-truth wording.

## Task 5 Integration and independent review

- [x] Run clinic test, lint, typecheck and build; fix real failures.
- [x] Review spec coverage separately from code quality, using independent agents and a requirement matrix.
- [x] Walk overview, resident, event, admin/import, handover and settings in the browser at desktop and phone sizes.
- [x] Test keyboard focus, responsive overflow, loading, empty, unavailable, wrong scope, failed save and same-browser multi-client updates. Full native zoom/assistive-technology verification remains a documented validation dependency.
- [x] Save screenshots as evidence outside committed source; fix visual inconsistencies before calling the design complete.
- [x] Run graphify update when tooling is available; if unavailable, report it without installing an unrelated stack.

## Task 6 PR and merge

Execution-time merge evidence is recorded in the GitHub pull request; this plan is committed before those steps occur.


- [ ] Create a focused reviewable PR with problem, implemented behavior, validation and truthful backend limitations. Attach it to this chat.
- [ ] Run the prescribed Greptile loop up to five iterations, fixing actionable feedback. Do not invent a score or disable checks.
- [ ] Rebase/update safely if needed and rerun affected checks on the merge candidate.
- [ ] Squash merge and delete the source branch when required checks and permissions allow.
- [ ] Verify the merged main commit includes the changes, preserve the primary hardware checkout, and leave a working preview.
- [ ] Complete the durable goal only after auditing actual frontend acceptance evidence and latest user merge instruction. Required missing production services or human validation remain explicitly recorded.
