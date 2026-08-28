# Phase 2 Backend Checkpoint B Review

**Decision:** Complete on August 27, 2026. Phase 2 overall remains in progress.

## What now works

The real Product API can show every tenant-owned monitoring device, its current
room/location assignment, latest operational state, last-seen time, per-source
state, and honest limitations. Device identity, assignment history, and health
observations survive application restart.

The implemented synthetic journey is:

1. The room has one resident and one assigned monitoring device.
2. An online device allows the latest otherwise-valid resident monitoring view.
3. Buffering and offline states remain operational device information and make
   current resident-specific monitoring unavailable.
4. Per-source limitations explain what is reduced without inventing a value.
5. A later online observation restores the latest valid monitoring view.
6. Historical awareness and resident events are not rewritten or fabricated.

## What the frontend can rely on

Rishit's replaceable clinic data client can use:

- `GET /v1/devices`
- `GET /v1/devices/{device_id}/health`
- the device/assignment/health fields composed into
  `GET /v1/residents/{resident_id}/status`

Known devices with no health history return `200 not_yet_available`. Missing
assignments, missing health, and unhealthy states are explicit. Unknown and
cross-tenant device IDs remain indistinguishable behind the same `404`.

## Product and safety checks

- Device health is operational state, not a resident diagnosis or warning.
- V1 permits one active room per device and one active device per room while
  preserving inactive assignment history.
- Offline, degraded, buffering, retrying, and assignment-unavailable states do
  not permit fake current resident measurements or baseline learning.
- A device state change does not create a resident event.
- Awareness history remains append-only when the current device state changes.
- All health policy and records in this checkpoint are visibly synthetic and
  test-only; no real heartbeat threshold was invented.

## How Akshar can verify it

Run:

```bash
python3 -m backend.app.checkpoints.device_health
```

The command creates a temporary migrated database, uses the real Product API,
walks through online → buffering → offline → online recovery, restarts the
application, and ends with `CHECKPOINT B READY` only when the complete product
behavior survives.

## Verification evidence

- founder Checkpoint A walkthrough: passed;
- founder Checkpoint B walkthrough: passed;
- full pytest suite: 276 passed plus 85 subtests;
- compatibility unittest suite: 75 passed;
- independent backend review: no critical or important findings;
- clinic frontend tests, lint, typecheck, and production build: passed;
- backend/test compilation and diff checks: passed.

## What remains

- **Checkpoint C:** notification/awareness preferences and versioned
  resident-memory administration;
- **Checkpoint D:** clinic-wide event query/handoff surface and frontend
  connection boundary;
- real ingestion, signal fusion, resident baselines from sensor data, anomaly
  intelligence, production auth, notification delivery, and deployment remain
  later work.
