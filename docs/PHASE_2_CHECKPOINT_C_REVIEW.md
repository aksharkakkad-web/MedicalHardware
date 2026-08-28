# Phase 2 Backend Checkpoint C Review

**Decision:** Implementation complete on August 27, 2026. Phase 2 overall
remains in progress.

## What now works

The real Product API now gives authorized development clinic operators two
resident-level controls:

1. versioned choices for future watch/high/critical event delivery and
   away/return/limited/unavailable awareness delivery;
2. versioned resident-memory actions to add, correct, or retire context.

A resident without saved preferences is shown honestly as not yet configured.
Every preference or memory change records the tenant, actor, time, version,
idempotency result, and audit effect in one transaction.

## Locked product behavior

- Delivery preferences control future notification noise only. Phase 2 does
  not send real notifications.
- High and critical events always remain visible in the clinic dashboard even
  if separate delivery is turned off.
- Direct memory entries are visibly operator-sourced and never pretend to come
  from event feedback.
- A correction retires the inaccurate entry and creates a linked replacement.
- A retirement preserves the entry and its reason instead of deleting it.
- Old memory and preference versions remain durable and auditable.
- Resident memory remains separate from numerical calibration, past event
  evidence, warning thresholds, and global behavior.
- Production authentication and role authorization remain later scope; Phase 2
  uses the documented development tenant/actor headers.

## What Rishit can rely on

Rishit's replaceable frontend client can use:

- `GET /v1/residents/{resident_id}/notification-preferences`
- `PUT /v1/residents/{resident_id}/notification-preferences`
- `GET /v1/residents/{resident_id}/memory`
- `POST /v1/residents/{resident_id}/memory/entries`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/correct`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/retire`

The exact V1.6 request/response shapes are frozen in `docs/DATA_CONTRACT.md`.
Stale versions return a stable conflict, exact replays do not repeat effects,
changed requests cannot reuse an idempotency key, and cross-tenant records are
masked behind the same not-found response as missing records.

## How Akshar can verify it

Run:

```bash
python3 -m backend.app.checkpoints.preferences_memory
```

The command creates a temporary migrated database, starts with honest missing
preferences, changes delivery choices, proves a high event remains on the
dashboard, adds/corrects/retires memory, restarts the application, and ends
with `CHECKPOINT C READY` only when every current and historical effect
survives.

## Verification evidence

- founder Checkpoints A, B, and C walkthroughs: passed;
- full pytest suite: 333 passed plus 85 subtests;
- compatibility unittest suite: 76 passed;
- clinic frontend: 14 tests, lint, typecheck, and production build passed;
- independent review: initial Important findings were fixed and the re-review
  reported no remaining Critical or Important issues;
- migration up/down, tenant, concurrency, idempotency, rollback, restart,
  strict-contract, and prior-feedback compatibility checks: passed;
- backend compilation and diff checks: passed.

## What remains

- **Checkpoint D:** clinic-wide event filters/pagination, complete OpenAPI
  handoff, and the real frontend-client connection boundary;
- real notification delivery, production authentication, memory-history UI,
  active-learning prompts, baseline consumption, global system learning,
  ingestion, signal fusion, anomaly intelligence, deployment, and clinical
  validation remain later work.
