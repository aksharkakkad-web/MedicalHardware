# Phase 2 Checkpoint B Device Assignment and Health Plan

**Status:** Complete
**Owner:** Akshar — backend and product intelligence
**Depends on:** Checkpoint A merged on `main`
**Outcome:** The clinic product can show which device belongs to a room, its
latest honest operating state, and how that state affects resident monitoring.

## Product decisions frozen for this checkpoint

- Device health is operational information, separate from resident health.
- A device can have only one active room assignment, and a room can have only
  one active device assignment in V1.
- Assignment and health history are append-only.
- Product health states are `online`, `offline`, `degraded`, `buffering`,
  `retrying`, and `assignment_unavailable`.
- Missing health data is shown as `not_yet_available`; the backend does not
  invent an online/offline state.
- Per-source state and limitations are visible without exposing vendor payloads.
- Any current device state other than `online` makes resident-specific current
  monitoring unavailable. A later `online` observation allows the latest valid
  resident monitoring snapshot to be shown again.
- Device problems do not create resident warning events in this checkpoint.
- Records are synthetic and test-only. Real telemetry ingestion and clinical
  thresholds remain later work.

## Task 1 — Freeze the device product contract and domain rules

**Create:**

- `backend/app/domain/device_health.py`
- `backend/app/contracts/devices.py`
- `tests/device_health_domain/test_device_health.py`
- `tests/api/test_device_contracts.py`

**Update:**

- `backend/app/contracts/__init__.py`
- `docs/DATA_CONTRACT.md`

**Test first:**

- accept each approved product health state;
- require strict UTC observation and last-seen times;
- reject last-seen times after the observation;
- require unique, nonblank sensor-source names;
- reject malformed booleans, blank limitations, extra fields, and unknown
  schema versions;
- prove exact list and detail response fields, including honest
  `not_yet_available` behavior.

**Contract shape:**

- `DeviceHealthResponse` includes device identity, data availability, nullable
  current state/time fields, per-source health, limitations, and a visible
  synthetic/test-only marker.
- `DeviceListItemResponse` includes the device, current room/location
  assignment if present, and the same latest health summary.
- `DeviceListResponse` contains ordered items.
- Resident status receives a nullable device summary plus explicit device
  availability reasons; database rows never leak into the public contract.

**Done when:** focused domain and contract tests pass and the shared contract
contains exact JSON examples for available, unavailable, and unassigned cases.

## Task 2 — Persist locations, device assignments, and health history

**Create:**

- `backend/app/db/migrations/versions/0003_device_health.py`
- `backend/app/db/device_mappers.py`
- `backend/app/db/device_repositories.py`
- `tests/persistence/test_device_schema.py`
- `tests/persistence/test_device_repositories.py`

**Update:**

- `backend/app/db/models.py`
- `tests/persistence/test_migrations.py`
- `tests/persistence/test_restart_durability.py`

**Test first:**

- migration creates durable locations, devices, device-room assignment history,
  and append-only health observations;
- composite ownership constraints reject cross-tenant relationships;
- partial unique indexes permit history but reject two active rooms for one
  device or two active devices for one room;
- latest health uses `observed_at` plus a deterministic record tie-breaker;
- history remains chronological and survives application restart;
- malformed stored JSON fails loudly rather than becoming fake precision.

**Done when:** persistence proves tenant isolation, assignment uniqueness,
append-only history, restart durability, and exact mapper round trips.

## Task 3 — Expose tenant-safe clinic device reads

**Create:**

- `backend/app/services/device_queries.py`
- `backend/app/api/v1/devices.py`
- `tests/api/test_device_read_api.py`

**Update:**

- `backend/app/api/dependencies.py`
- `backend/app/api/v1/router.py`
- `tests/api/test_contracts.py`

**Paths:**

- `GET /v1/devices`
- `GET /v1/devices/{device_id}/health`

**Test first:**

- list order and exact current assignment/health response;
- current health detail and per-source limitations;
- known device with no observations returns `200 not_yet_available`;
- unknown and cross-tenant device IDs return the same `404` envelope;
- unsupported methods and missing headers use versioned error envelopes;
- OpenAPI names the exact response models.

**Done when:** the dashboard can discover every tenant-owned device and render
its honest current state without database knowledge.

## Task 4 — Compose device truth into resident status

**Update:**

- `backend/app/contracts/status.py`
- `backend/app/services/status_queries.py`
- `backend/app/api/dependencies.py`
- `tests/api/test_status_read_api.py`
- `tests/api/test_status_contracts.py`
- `docs/DATA_CONTRACT.md`

**Test first:**

- an assigned online device preserves the latest resident monitoring state;
- offline, degraded, buffering, and retrying states make current resident
  monitoring unavailable without changing historical awareness;
- a missing/conflicting device assignment is explicit
  `assignment_unavailable`;
- missing device-health history is explicit and never treated as online;
- a later online observation restores the latest valid monitoring view;
- no device condition creates a resident event.

**Done when:** a single resident status read gives the frontend coherent
monitoring, calibration, assignment, and device truth.

## Task 5 — Seed and prove the complete Checkpoint B story

**Create:**

- `backend/app/checkpoints/device_health.py`
- `tests/api/test_device_health_story.py`

**Update:**

- `backend/app/db/seed.py`
- `backend/app/checkpoints/__init__.py`
- `tests/persistence/test_seed.py`

**Founder command:**

```bash
python3 -m backend.app.checkpoints.device_health
```

The command must print plain-language PASS lines for:

1. device is assigned to the resident's room;
2. online state allows current monitoring;
3. buffering/offline state is visible and monitoring becomes unavailable;
4. recovery returns the device online and monitoring resumes;
5. source limitations remain visible;
6. assignment and health history survive restart.

It ends with `CHECKPOINT B READY` only when all product behaviors pass.

## Task 6 — Review, document, merge, and continue

**Create:**

- `docs/PHASE_2_CHECKPOINT_B_REVIEW.md`

**Update:**

- `docs/CURRENT_STAGE.md`
- `docs/PHASE_2_REVIEW.md`
- `docs/BUILD_PLAN.md`
- this plan
- `graphify-out/`

**Verification:**

```bash
python3 -m backend.app.checkpoints.device_health
python3 -m pytest -q
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q backend tests
git diff --check
pnpm --dir apps/clinic-dashboard test
pnpm --dir apps/clinic-dashboard lint
pnpm --dir apps/clinic-dashboard typecheck
pnpm --dir apps/clinic-dashboard build
```

Then:

1. independently review product honesty, tenant isolation, assignment
   uniqueness, contract completeness, and restart behavior;
2. fix findings test-first;
3. push one PR and run Greptile until 5/5 with zero unresolved actionable
   comments, up to five iterations;
4. squash merge and delete the branch;
5. verify the founder command and full suite from clean `main`;
6. begin Checkpoint C without waiting for routine approval.

## Non-goals

- real device authentication or telemetry ingestion;
- hardware/vendor payload parsing;
- real network heartbeat thresholds;
- notification delivery;
- resident anomaly or medical inference;
- device-generated resident warning events;
- production deployment.
