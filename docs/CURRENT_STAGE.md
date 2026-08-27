# Current Project Stage

**Updated:** August 27, 2026

**Operating status:** Phase 1 product logic is complete. Phase 2 is **In
progress**. The first durable event slice plus backend Checkpoints A (resident
status/calibration) and B (device assignment/health) are complete. Backend
Checkpoint C—preferences and resident-memory administration—is next. Frontend
and hardware work continue independently. See `docs/PHASE_GATES.md` for the
shared start → build → review → merge → next-checkpoint process.

## Where we are now

We have finished the Phase 1 behavior milestone, the first durable Phase 2
event slice, and Phase 2 backend Checkpoints A and B using synthetic data.

This is not the complete deployed product yet. The caregiver product backbone
now has a file-backed database, versioned Product API, durable lifecycle and
feedback transactions, resident monitoring/awareness history, versioned
calibration/setup history, device/location/room assignment history, append-only
device health, tenant isolation, idempotency, audit history, and restart proofs.
The frontend, settings/memory-admin checkpoint, final clinic handoff, and real
hardware remain unfinished.

The tested journey is:

1. A room has one assigned resident.
2. The system decides whether resident monitoring is active, paused because the resident is away, limited because another person may be present, or unavailable because conditions are unreliable.
3. Clean resident-present periods can build calibration; unreliable, away, visitor, concerning, or unresolved periods cannot teach the personal baseline.
4. A concerning pattern creates an event that can be grouped, prioritized, marked overdue, acknowledged, checked, and resolved.
5. Operator feedback can update resident context without rewriting event history or automatically changing safety rules.
6. A repeated pattern creates a new linked event instead of reopening the resolved one.
7. Setup changes can recalibrate only the affected sensing dimensions while preserving resident history and unaffected progress.
8. Current device assignment and health are composed into resident status, so
   known device trouble stops current monitoring without rewriting history.
9. Device recovery restores the latest otherwise-valid resident monitoring
   view.

The Product API now also persists and exposes active, away, return,
possible-multi-person, and unavailable/limited monitoring history. A setup
change can restart only an affected calibration dimension while preserving
unaffected progress and all history. An assigned resident whose histories have
not started is shown honestly as not yet available instead of being mistaken
for a missing resident. The plain-language verification command is
`python3 -m backend.app.checkpoints.status_calibration`.

The Product API also exposes device lists and health detail. Online, offline,
degraded, buffering, retrying, assignment-unavailable, and not-yet-available
conditions stay explicit. The device verification command is
`python3 -m backend.app.checkpoints.device_health`.

## What Rishit can build now

Rishit does not need to wait for the database, API, or hardware.

He can build the real clinic dashboard and separate home experience against contract-valid mock data, including:

- room and resident status;
- active, away, limited, and unavailable monitoring states;
- calibration and recalibration states;
- event priority, recurrence, overdue state, and history;
- acknowledge, check, and resolve actions;
- feedback and resident-context editing;
- settings for awareness items and notifications;
- device assignment, health, last-seen, and honest per-source limitations.

The frontend should place mock data behind a replaceable client/provider. Later, the real backend API replaces that mock provider without redesigning the screens.

The clinic caregiver experience is the first complete user journey. Rishit can build the full separate home experience on mocks now; Phase 7 later connects and validates that existing experience against mature monitoring data and family-safe permissions rather than rebuilding it.

## What Akshar builds next

The first durable Product API slice and Checkpoints A–B are implemented. Akshar's
remaining Phase 2 backend checkpoints are:

- **Checkpoint C:** notification/awareness preferences and versioned resident
  memory administration;
- **Checkpoint D:** clinic-wide event filters/pagination, complete OpenAPI
  handoff, and a real-client connection boundary for Rishit.

Simulated telemetry ingestion, fusion, baselines, anomaly/confidence logic,
notifications, and selective AI interpretation remain later slices and phases.

## What the hardware track builds in parallel

The hardware engineer can continue radar, thermal, and Wi-Fi CSI bring-up independently. The device should produce the versioned compact telemetry boundary documented for both simulation and real hardware.

Real hardware later replaces the simulator as the telemetry producer. It should not require the frontend flow or backend product logic to be rebuilt.

## Where the tracks reconnect

- **Frontend ↔ backend:** the mock frontend client is replaced by the real API client using the same shared contract.
- **Hardware ↔ backend:** the simulator is replaced by real device telemetry using the same ingestion boundary.
- **All tracks:** run the agreed scenarios with toy data first, then simulated telemetry, then real hardware data.

## Important locked decisions

- V1 supports one assigned resident per room.
- RFID and wearable identity are out of scope.
- Possible multiple-person periods reduce or pause resident-specific monitoring; the system does not guess identity.
- Low-quality data becomes limited or unavailable rather than fake precision.
- Synthetic thresholds are test-only, not clinical or production policy.
- Resolved events remain immutable; recurrences create new linked history.
- Resident memory and the numerical baseline are separate.

## Source-of-truth handoff

- Phase status, review gates, and team cadence: `docs/PHASE_GATES.md`
- Product behavior: `docs/PRD.md`
- System boundaries: `docs/ARCHITECTURE.md`
- Shared frontend/backend/hardware language: `docs/DATA_CONTRACT.md`
- Build order: `docs/BUILD_PLAN.md`
- Ownership: `docs/TEAM_OWNERSHIP.md`
- Checkpoint A evidence: `docs/PHASE_2_CHECKPOINT_A_REVIEW.md`
- Checkpoint B evidence: `docs/PHASE_2_CHECKPOINT_B_REVIEW.md`
