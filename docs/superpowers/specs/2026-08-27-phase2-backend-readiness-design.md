# Phase 2 Backend Readiness Design

**Status:** Approved in conversation on August 27, 2026  
**Owner:** Akshar — backend and intelligence  
**Frontend handoff owner:** Rishit  
**Target gate:** Backend ready for the first clinic-dashboard API connection

## 1. Outcome

Complete the remaining Phase 2 backend product-state work on top of the
durable event backbone. At the end, Rishit can replace the clinic dashboard's
mock provider for the agreed resident/event journey without redesigning the
frontend.

The backend will persist and expose:

- resident monitoring and presence state;
- awareness history for away, return, limited, and unavailable periods;
- calibration progress and monitoring-setup history;
- device identity, room assignment, and product-facing health state;
- administrator notification and awareness preferences;
- authorized, versioned resident-memory editing;
- the clinic event queue and the existing event lifecycle.

The home experience remains on its contract-valid mock provider until the
later home real-data phase.

## 2. Existing Foundation to Extend

The implementation extends these existing units:

- `backend/app/domain/monitoring.py` already derives active, limited, paused,
  and unavailable monitoring states from assignment, presence, device health,
  and test-only quality policy.
- `backend/app/domain/calibration.py` already models new, calibrating, partial,
  and established calibration, excluded learning windows, setup versions, and
  selective recalibration.
- `backend/app/domain/events.py` already owns event grouping, priority,
  recurrence, overdue behavior, and lifecycle rules.
- `backend/app/domain/feedback.py` already separates trusted feedback,
  resident semantic memory, and controlled baseline eligibility.
- The Phase 2 Product API and database already persist assignments, events,
  actions, feedback, memory, idempotency, and audit history.

No parallel backend abstraction will be created. Domain rules stay separate
from persistence and public API representation.

## 3. Delivery Shape

The work is divided into four independently reviewable checkpoints. Each
checkpoint ends with focused tests, the full regression suite, documentation,
and a product-level walkthrough.

### Checkpoint A — Resident state, awareness, and calibration

Persist append-only resident monitoring snapshots. Each snapshot records the
resident, room, presence state, monitoring state, learning eligibility,
measurement eligibility, reason codes, observation time, and the versioned
test-only quality policy when synthetic data produced it.

The same history is the awareness timeline. Resident-away is an awareness
state, not a warning or concerning resident event. A return to
`resident_present` is recorded as a normal timeline transition. Limited,
paused, and unavailable states explain why resident-specific monitoring is
reduced without inventing a measurement.

Persist current calibration progress as versioned snapshots plus append-only
monitoring-setup changes. A setup change records the previous and new setup
versions, reason, actor, time, and affected sensing dimensions. Only affected
dimensions return to calibration; resident history, event history, and
semantic memory remain.

Public clinic reads:

- `GET /v1/residents/{resident_id}/status`
- `GET /v1/residents/{resident_id}/awareness`
- `GET /v1/residents/{resident_id}/calibration`

Authorized clinic action:

- `POST /v1/residents/{resident_id}/setup-changes`

The setup-change action is versioned, idempotent, audited, UTC-only, and
tenant-scoped.

### Checkpoint B — Device assignment and health

Add durable locations, devices, and device-to-room assignment history.
Assignments are tenant-safe and permit history while allowing only one active
room per device and one active device assignment per room for this V1 flow.

Persist append-only device health observations. The product-facing state
supports:

- `online`;
- `offline`;
- `degraded`;
- `buffering`;
- `retrying`;
- `assignment_unavailable`.

Each record includes observation time, last-seen time, per-source health, and
honest limitations. Hardware-specific payload formats remain behind the
future edge adapter. Phase 2 uses synthetic records and does not infer sensor
measurements.

Public clinic reads:

- `GET /v1/devices`
- `GET /v1/devices/{device_id}/health`

Resident status composes the current assignment, latest monitoring snapshot,
calibration state, and relevant device health without coupling the API to
database rows.

### Checkpoint C — Preferences and resident-memory administration

Persist one current notification/awareness preference set per resident with
version history. Settings cover watch/high/critical delivery preferences and
away, return, limited, and unavailable awareness notifications. Preferences
control delivery and noise; they never hide high or critical events from the
clinic dashboard. Notification delivery itself is later scope.

Expose authorized resident-memory commands to add, correct, or retire an
entry. Corrections create a new memory version, retire the superseded entry,
and preserve source and actor history. No command deletes memory history.

Public clinic reads/actions:

- `GET /v1/residents/{resident_id}/notification-preferences`
- `PUT /v1/residents/{resident_id}/notification-preferences`
- `POST /v1/residents/{resident_id}/memory/entries`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/correct`
- `POST /v1/residents/{resident_id}/memory/entries/{entry_id}/retire`

Every mutation is versioned, idempotent, audited, UTC-only, tenant-scoped,
and committed atomically with its history.

### Checkpoint D — Clinic API handoff

Complete the clinic queue and product handoff surface:

- `GET /v1/events` with tenant-safe status, priority, resident, and room
  filters;
- the resident, event, monitoring, calibration, device, preference, and
  memory paths from Checkpoints A–C;
- the existing acknowledge, check, resolve, and feedback actions;
- one generated OpenAPI document representing the real backend contract.

Trend intelligence is not fabricated in Phase 2. A trend read may report an
honest unavailable/not-yet-produced state if the frontend contract requires
the path before Phase 5 intelligence exists.

The handoff is complete when the synthetic clinic story can use only the real
Product API for the selected connection path and Rishit does not need database
knowledge or a UI redesign.

## 4. Data Boundaries

### Append-only history

Monitoring snapshots, setup changes, calibration snapshots, device health,
preference versions, memory versions, event actions, feedback, and audit
records are historical facts. New facts append; corrections never rewrite old
facts.

### Current state

Repositories calculate current state by selecting the latest complete,
tenant-owned version. Public responses contain product concepts rather than
ORM models.

### Tenant ownership

Composite ownership constraints bind every resident, room, device,
assignment, status, calibration, setting, and child record to the same tenant.
Cross-tenant lookups return the same not-found response as missing IDs.

### Contract versioning

All new public objects and mutation bodies use `schema_version: "1.0"` and
strict UTC timestamps. Additive endpoints do not change the semantics of the
already frozen first-slice responses. Any shared contract change is recorded
in `docs/DATA_CONTRACT.md` in the same checkpoint.

## 5. Service and Transaction Boundaries

Queries compose read models from repositories and never mutate data.
Commands own one database transaction containing the product change,
idempotency record, and audit record.

Concurrent updates use explicit versions. A stale preference, calibration,
setup, or memory command returns a stable conflict instead of overwriting a
newer decision. Replaying the same idempotency key and logical request returns
the stored response without repeating effects; reusing it for a different
request returns an idempotency conflict.

## 6. Failure Behavior

- Invalid tenant ownership behaves like a missing resource.
- Invalid state changes return a stable conflict and create no partial
  history.
- Missing or unhealthy device conditions make monitoring unavailable rather
  than creating fake resident values.
- Resident-away pauses resident-specific learning and measurements but remains
  visible in awareness history.
- Possible multi-person presence limits monitoring and never guesses identity.
- Database or audit failures roll back the full command.
- Test-only thresholds remain visibly marked synthetic and are never presented
  as clinical policy.

## 7. Verification and Founder Testing

Every checkpoint has five evidence levels:

1. **Rule tests** prove monitoring, calibration, settings, and lifecycle
   invariants in isolation.
2. **Persistence tests** prove migrations, tenant ownership, concurrency,
   atomic rollback, and restart durability.
3. **Contract/API tests** prove exact versioned responses, strict inputs,
   idempotency, errors, filters, and cross-tenant behavior.
4. **Product acceptance story** walks through a synthetic resident becoming
   active, leaving, returning, experiencing limited monitoring, undergoing a
   setup change, showing device trouble and recovery, changing preferences,
   editing memory, and completing an event journey.
5. **Independent review** runs the full repository suite and Greptile loop
   until 5/5 confidence with zero unresolved actionable comments.

A human-readable checkpoint command will print each product behavior as
`PASS` or fail with a plain-language reason. `docs/CURRENT_STAGE.md` and a
Phase 2 readiness review will state what works, what remains synthetic, and
what Rishit can connect.

## 8. Merge and Progress Loop

For each checkpoint:

1. write a failing acceptance test;
2. implement the smallest complete product behavior;
3. run focused and full tests;
4. run the human-readable product walkthrough;
5. review contract, safety, tenant, and ownership boundaries;
6. fix findings and rerun checks;
7. update the source-of-truth status;
8. merge the reviewed checkpoint;
9. begin the next checkpoint from clean `main`.

Routine implementation choices do not require founder approval. Work pauses
only for a new product decision, an active shared-contract conflict with
Rishit, or evidence that the approved scope cannot be implemented safely.

## 9. Explicit Non-Goals

This runway does not implement:

- real or simulated edge-telemetry ingestion;
- cross-sensor fusion;
- numerical personal-baseline learning from signals;
- anomaly detection or real warning thresholds;
- LLM interpretation;
- notification delivery channels;
- production authentication/authorization;
- mature home/family real-data permissions;
- deployment, clinical validation, or medical claims;
- real hardware integration.

Those remain in later documented phases. Phase 2 may store synthetic product
states needed for frontend integration, but it does not pretend the later
intelligence already exists.

## 10. Completion Gate

The backend runway is ready for Rishit when:

- all four checkpoints are merged and green;
- current and historical product state survives restart;
- tenant and concurrency tests pass;
- the clinic acceptance story passes through the real API;
- the published contract matches the backend OpenAPI surface;
- the full suite and independent review pass;
- the handoff document identifies the exact frontend client operations;
- no unresolved product decision remains inside the approved Phase 2 scope.

The next action is frontend integration, not additional hidden backend scope.
