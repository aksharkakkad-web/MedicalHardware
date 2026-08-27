# Phase 2 Backend Checkpoint A Review

**Decision:** Complete on August 27, 2026. Phase 2 overall remains in progress.

## What now works

The real Product API can show a caregiver whether resident monitoring is
active, paused, limited, or unavailable; why it is in that state; the ordered
awareness history; and current calibration progress. The same synthetic story
works before and after an application restart.

The implemented flow is:

1. Resident monitoring is active and learning is allowed.
2. Resident-away is recorded as awareness, not a warning event.
3. Returning to the room resumes active monitoring.
4. Possible multi-person presence limits resident-specific monitoring and
   prevents that period from teaching the baseline.
5. Established calibration is visible by sensing dimension.
6. An authorized setup change can restart only `movement` calibration while
   preserving respiratory-rate progress and all earlier history.

## What the frontend can rely on

Rishit's replaceable clinic data client can use these frozen paths:

- `GET /v1/residents/{resident_id}/status`
- `GET /v1/residents/{resident_id}/awareness`
- `GET /v1/residents/{resident_id}/calibration`
- `POST /v1/residents/{resident_id}/setup-changes`

Responses are versioned, UTC-only, tenant-safe, and documented in OpenAPI and
`docs/DATA_CONTRACT.md`. Setup changes are idempotent and version checked, so
a retry returns the original response and an outdated dashboard edit cannot
overwrite newer progress.

## Safety and honesty checks

- Away and possible-multi-person periods never become invented resident
  measurements.
- Away remains an awareness item rather than an event requiring response.
- An assigned resident whose monitoring history has not started is shown as
  unavailable rather than being mistaken for a missing resident.
- Cross-tenant and missing resident records are indistinguishable.
- Status, calibration, setup history, idempotency, and audit effects commit or
  roll back together.
- Synthetic quality/calibration policy is explicitly test-only and is not a
  clinical threshold.

## How Akshar can verify it

Run:

```bash
python3 -m backend.app.checkpoints.status_calibration
```

The command builds a temporary migrated database, runs the real API story,
restarts the app, verifies exact retry behavior, and ends with
`CHECKPOINT A READY` only when every product-level check passes.

## Verification evidence

- founder Checkpoint A walkthrough: passed;
- full pytest suite: 213 passed plus 83 subtests;
- compatibility unittest suite: 75 passed;
- backend/test compilation and diff checks: passed.

## What remains

- **Checkpoint B:** device assignment and device-health behavior;
- **Checkpoint C:** notification preferences and resident-memory
  administration;
- **Checkpoint D:** clinic-wide event query/handoff surface and frontend
  connection boundary;
- frontend, hardware, ingestion, monitoring intelligence, production auth,
  notification delivery, and deployment continue on their documented tracks.
