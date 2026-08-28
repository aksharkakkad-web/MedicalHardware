# Phase 2 Checkpoint D — Clinic API Handoff Plan

**Status:** Complete
**Owner:** Akshar — backend and intelligence
**Frontend handoff owner:** Rishit
**Outcome:** The clinic dashboard can replace its selected mock-data paths with
the real Product API without database knowledge or a product-flow redesign.

## Locked product decisions

- The default clinic queue contains active work: open, acknowledged, and
  checked events. Resolved history is explicitly requestable.
- Status and priority support repeated multi-select filters. Resident and room
  are optional single filters. Categories combine with AND.
- The queue is ordered for caregiver attention: unresolved, priority,
  overdue, newest signal, newest creation, then event identity.
- Pagination uses opaque keyset cursors bound to the tenant and active filters.
  Page size defaults to 25 and is capped at 100. Repeated single-value
  parameters are rejected rather than silently choosing one.
- Cross-tenant filter identifiers return an empty page and reveal nothing.
- High and critical events remain in the dashboard queue regardless of
  delivery preferences.
- Trends, clinical thresholds, signal evidence, AI interpretation, production
  authentication, notification sending, and home real-data access are not
  invented in this checkpoint.
- Rishit owns `ApiMonitoringClient`, browser routing/proxy behavior, and UI
  composition. Akshar supplies exact operations, OpenAPI, examples, and the
  composition map without editing the frontend application.

## Task 1 — Freeze the queue and handoff contract

- Record filters, defaults, ordering, pagination, failure behavior, and honest
  non-goals in `docs/DATA_CONTRACT.md`.
- Add strict queue response and cursor/query boundaries without changing the
  existing resident history response.
- Freeze stable OpenAPI operation IDs for frontend generation and debugging.

**Proof:** contract tests reject unknown fields, invalid limits, internal
statuses, malformed cursors, and filter/cursor mismatches.

## Task 2 — Build tenant-safe queue persistence

- Query only events owned by the current tenant.
- Apply status, priority, resident, and room filters at the database boundary.
- Return the exact total plus one bounded page in stable attention order.
- Use keyset pagination with no duplicates or gaps across an unchanged data
  set, and batch-hydrate event histories for the page.

**Proof:** persistence tests cover every filter, combinations, ties, pages,
empty cross-tenant filters, total count, and deterministic ordering.

## Task 3 — Expose the real clinic queue

- Add `GET /v1/events` with versioned success and error envelopes.
- Preserve the existing `GET /v1/events/{event_id}` and lifecycle actions.
- Validate repeated query values and convert cursor failures into stable
  `422 invalid_input` responses.
- Prove lifecycle actions immediately change active queue membership while
  preserving resolved history.

**Proof:** API tests cover exact JSON, headers, filters, pagination, tenant
masking, preference visibility, lifecycle refresh, and method errors.

## Task 4 — Generate and lock the Product API document

- Export one deterministic `docs/openapi/product-api-v1.json` from the real
  FastAPI application.
- Add a drift test that fails when runtime routes and the committed document
  disagree.
- Ensure every route documents development headers, request/response types,
  stable operation IDs, and versioned 404/405/409/422/500 behavior as
  applicable.

**Proof:** a clean export produces no diff, and the OpenAPI test compares the
  committed artifact with runtime generation.

## Task 5 — Prove the complete synthetic clinic API story

- Add `python3 -m backend.app.checkpoints.clinic_handoff`.
- Walk multiple synthetic rooms/residents/events through queue filters and
  pages, event detail, lifecycle actions, feedback, status, calibration,
  device health, preferences, and resident memory using HTTP only.
- Recreate the application against the same database and prove the story and
  queue remain durable.

**Proof:** every behavior prints `PASS`, then `CHECKPOINT D READY`.

## Task 6 — Publish Rishit's exact connection map

- Map each `MonitoringClient` need to Product API operations and public fields.
- Define how the overview composes resident identity, current monitoring,
  device state, active event count, highest attention priority, and headline.
- Record honest nullable/missing behavior and the complete device-state map.
- State that same-origin proxy/CORS choice and `ApiMonitoringClient` remain in
  Rishit's frontend lane.

**Proof:** Rishit needs no database knowledge and no hidden backend assumption;
the next action is a frontend adapter, not another backend product decision.

## Task 7 — Review, verify, and merge

- Run focused tests, full pytest, unittest compatibility, backend compilation,
  founder walkthrough, frontend regression checks, and `git diff --check`.
- Refresh Graphify after source changes.
- Run independent code/product review, fix findings, then open one short-lived
  PR and reach Greptile 5/5 with zero unresolved actionable comments.
- Squash-merge, verify the founder command from clean `main`, and update the
  source-of-truth status to show the Phase 2 backend runway complete.

## Completion gate

Checkpoint D is complete only when the real clinic queue, generated OpenAPI,
restart-safe HTTP walkthrough, exact frontend handoff, full test suite,
independent review, and merge gate all pass. The remaining work then belongs
at the frontend connection checkpoint, not to hidden Phase 2 backend scope.
