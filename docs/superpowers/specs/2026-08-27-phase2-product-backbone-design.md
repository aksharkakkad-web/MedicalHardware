# Phase 2 Product Backbone — First Vertical Slice Design

**Status:** Ready for founder review

**Phase:** Phase 2 — first complete event experience

## Purpose

Phase 1 proved the product rules with deterministic in-memory toy data. This first Phase 2 backend slice makes one caregiver event journey durable and accessible without expanding into sensor intelligence, AI, notifications, or production deployment.

The product proof is simple: after the backend restarts, the room/resident assignment, event, caregiver actions, feedback, resident memory, and audit history are still present and still obey the Phase 1 rules.

## Phase 1 gate result

Phase 1 passed its gate:

- the complete toy journey runs end to end;
- missing assignment, resident-away, possible-multi-person, and poor-quality situations fail safely;
- calibration, event history, recurrence, feedback, memory, and correction behavior are covered;
- the shared contracts and ownership boundaries are documented;
- all 72 tests pass on merged `main`.

Database, API, frontend, hardware, authentication, notifications, real sensor ingestion, monitoring intelligence, and clinical validation were intentionally deferred.

## Selected approach

Build one contract-first vertical slice using:

- FastAPI for the Product API;
- Pydantic request/response contracts;
- SQLAlchemy 2 for durable storage;
- Alembic for versioned migrations;
- a database URL boundary that supports Postgres/Supabase for shared environments and SQLite for deterministic local tests;
- the existing `backend/app/domain/` modules as the product-rules core.

No live Supabase project or credentials are required for this slice. The persistence boundary must remain Postgres-compatible so a Supabase-hosted Postgres database can replace the local database without changing the Product API or domain behavior.

## Reuse boundary

The implementation extends rather than rewrites Phase 1:

- `monitoring.py` remains the authority for monitoring suitability;
- `calibration.py` remains the authority for calibration and recalibration;
- `events.py` remains the authority for event grouping, lifecycle, overdue behavior, recurrence, and chronology;
- `feedback.py` remains the authority for feedback, learning eligibility, and resident-memory correction;
- `toy_scenario.py` remains the golden product walkthrough.

New database and API adapters may map to these objects, but they must not create a parallel set of product rules.

## First end-to-end story

The seeded development story contains one synthetic tenant, one room, one assigned resident, and one open high-priority event.

A development access context representing an authorized clinic operator can:

1. view the resident and room status;
2. list and open the event;
3. acknowledge the event;
4. record that it was checked;
5. resolve it with an allowed resolution outcome;
6. submit trusted structured feedback;
7. view the resulting resident-memory version and complete event history;
8. restart the backend;
9. retrieve the same assignment, event, actions, feedback, and memory afterward.

The slice must also prove that invalid lifecycle actions, out-of-order history, duplicate retries, and cross-tenant access fail safely.

## Initial durable records

Only records needed for the first story are included:

- tenant;
- room;
- resident;
- room-to-resident assignment;
- monitoring event;
- event action history;
- event priority history;
- feedback record;
- resident-memory snapshot and entries;
- an audit record for every state-changing API action.

Calibration persistence, setup-change history, awareness timeline, devices, device health, interpretation, notification preferences, and broader CRUD are later Phase 2 slices. Their absence does not change the existing in-memory domain behavior.

## First Product API

### Read paths

- `GET /health`
- `GET /v1/residents`
- `GET /v1/residents/{resident_id}`
- `GET /v1/residents/{resident_id}/events`
- `GET /v1/residents/{resident_id}/memory`
- `GET /v1/events/{event_id}`

### Caregiver actions

- `POST /v1/events/{event_id}/acknowledge`
- `POST /v1/events/{event_id}/checked`
- `POST /v1/events/{event_id}/resolve`
- `POST /v1/events/{event_id}/feedback`

The API returns explicit `schema_version`, UTC timestamps, actor history, priority history, recurrence fields, resident/room identifiers, status, and product limitations required by this slice.

## Temporary access boundary

Production authentication is outside this slice. Every request still carries an explicit tenant and actor context through development-only headers:

- `X-Tenant-Id`
- `X-Actor-Id`

The application treats the actor as an authorized clinic administrator for this synthetic slice. Records are always filtered by tenant. A record belonging to another tenant returns not found rather than revealing its existence.

This boundary is replaceable by real authentication later; business services must not depend on header parsing directly.

## Idempotency and chronology

Every state-changing request requires `Idempotency-Key`.

- Repeating the same key and same logical request returns the original result without another action, feedback record, memory update, or audit effect.
- Reusing a key for a different logical request is rejected.
- All supplied timestamps must be timezone-aware and must not precede the latest event history.
- Resolved events remain immutable; a later recurrence is a separate linked event.

## Product response boundary

The database model is not the API model. API responses use dedicated versioned contracts so Rishit's mock client and the future real client can share the same meanings without depending on database columns.

The first slice freezes only fields required for the caregiver journey. Broader evidence, interpretation, device-health, trends, and home-specific views remain documented but are not falsely returned as working data.

## Failure behavior

The Product API uses one versioned error envelope containing:

- stable machine-readable error code;
- plain-language message;
- `schema_version`;
- optional field name when input is invalid.

Expected categories are invalid input, invalid transition, idempotency conflict, not found, and internal failure. Internal details and cross-tenant existence are never exposed.

## Transaction behavior

One caregiver action is one transaction. The event state/history, feedback, resident-memory version, idempotency record, and audit record either persist together or not at all.

The service layer owns transaction boundaries. API routes parse requests and return contracts; database repositories save/load records; domain modules decide whether behavior is allowed.

Mutable aggregate records carry an internal version. Concurrent requests must not both act on the same stale event or resident-memory version; one succeeds and the other receives a stable conflict response or an idempotent replay result.

## Test and review strategy

The slice is developed test-first and must include:

- migration/bootstrap test;
- repository round-trip and restart-durability tests;
- API contract tests for every listed route;
- full acknowledge → check → resolve → feedback journey test;
- invalid-transition and chronology tests;
- same-request idempotent retry and conflicting-reuse tests;
- cross-tenant isolation tests;
- rollback test proving partial feedback/memory/audit effects do not survive failure;
- concurrent stale-version test proving two conflicting actions cannot both commit;
- the existing 72 Phase 1 tests unchanged.

The review demo is product-level: run the full caregiver story, restart the application, and show the same event history and resident memory afterward.

## Non-goals

This slice does not include:

- real sensor ingestion, fusion, baselines, or anomaly generation;
- AI interpretation or feedback questions;
- notification delivery;
- production identity provider integration;
- real PHI;
- production hosting;
- clinical thresholds or claims;
- the frontend implementation;
- the complete conceptual database listed for later phases.

## Completion decision

This first slice is complete when the durable caregiver story and failure cases pass, the existing Phase 1 suite remains green, and the founder walkthrough confirms that the API behavior matches the agreed product flow.

Completing this slice starts Phase 2; it does not close all of Phase 2. Later slices add calibration/setup history, monitoring awareness, device health, notification settings, broader frontend contract coverage, and the remaining Phase 2 checkpoint work.
