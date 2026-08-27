# Current Project Stage

**Updated:** August 26, 2026

## Where we are now

We have finished the first backend behavior milestone using synthetic data.

This is not the complete deployed product yet. It is the working product logic that proves how the main monitoring journey should behave before we connect a database, product API, frontend, and real hardware.

The tested journey is:

1. A room has one assigned resident.
2. The system decides whether resident monitoring is active, paused because the resident is away, limited because another person may be present, or unavailable because conditions are unreliable.
3. Clean resident-present periods can build calibration; unreliable, away, visitor, concerning, or unresolved periods cannot teach the personal baseline.
4. A concerning pattern creates an event that can be grouped, prioritized, marked overdue, acknowledged, checked, and resolved.
5. Operator feedback can update resident context without rewriting event history or automatically changing safety rules.
6. A repeated pattern creates a new linked event instead of reopening the resolved one.
7. Setup changes can recalibrate only the affected sensing dimensions while preserving resident history and unaffected progress.

All of this currently runs in memory with deterministic toy data and automated tests.

## What Rishit can build now

Rishit does not need to wait for the database, API, or hardware.

He can build the real clinic dashboard and home experience against contract-valid mock data, including:

- room and resident status;
- active, away, limited, and unavailable monitoring states;
- calibration and recalibration states;
- event priority, recurrence, overdue state, and history;
- acknowledge, check, and resolve actions;
- feedback and resident-context editing;
- settings for awareness items and notifications.

The frontend should place mock data behind a replaceable client/provider. Later, the real backend API replaces that mock provider without redesigning the screens.

## What Akshar builds next

Akshar's next backend milestone is durable persistence and the Product API:

- store rooms, residents, calibration, events, audit history, feedback, and resident memory;
- expose the shared contract through the real API;
- add authentication and authorization boundaries;
- return the same shapes and lifecycle behavior the frontend already uses;
- keep the synthetic scenario as a repeatable backend evaluation.

After that come simulated telemetry ingestion, fusion, baselines, anomaly/confidence logic, notifications, and selective AI interpretation.

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

- Product behavior: `docs/PRD.md`
- System boundaries: `docs/ARCHITECTURE.md`
- Shared frontend/backend/hardware language: `docs/DATA_CONTRACT.md`
- Build order: `docs/BUILD_PLAN.md`
- Ownership: `docs/TEAM_OWNERSHIP.md`
