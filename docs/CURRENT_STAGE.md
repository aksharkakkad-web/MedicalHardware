# Current Project Stage

**Updated:** September 1, 2026

**Operating status:** Phase 1 product logic is complete. Phase 2 remains **In
progress**: its backend Checkpoints A through D are complete, while Rishit's
frontend convergence and hardware work remain independent and open. Akshar's
Phase 5 backend monitoring-intelligence lane is now **complete on deterministic
synthetic normalized fixtures**. The shared Phase 5 product gate is not closed
until its frontend and hardware exit work is reviewed. See
`docs/PHASE_GATES.md` for the shared start → build → review → merge →
next-checkpoint process.

## Where we are now

We have finished the Phase 1 behavior milestone, the first durable Phase 2
event slice, all four Phase 2 backend checkpoints, and the Phase 5 backend
monitoring-intelligence lane using synthetic data.

This is not the complete deployed product yet. The caregiver product backbone
now has a file-backed database, versioned Product API, durable lifecycle and
feedback transactions, resident monitoring/awareness history, versioned
calibration/setup history, device/location/room assignment history, append-only
device health, notification/awareness preference history, correctable resident
memory, tenant isolation, idempotency, audit history, and restart proofs. The
frontend connection, the complete user-facing experiences, and real hardware
remain unfinished.

Akshar's next independent backend layer is now implemented as the Monitoring
Intelligence Lab: a 12-cluster taxonomy, 120-case canonical set, deterministic
mass-case generator, strict Gemini 3.7 Flash adapter, feedback/memory skill
boundaries, hard safety grading, resumable redacted artifacts, and model
comparison/release gates. Campaign evidence is recorded separately from the
original 24-case Phase 5 proof. See `docs/MONITORING_INTELLIGENCE_LAB.md`.

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
10. Staff can change future event/awareness delivery choices without hiding
    high or critical events from the clinic dashboard.
11. Staff can add, correct, or retire resident context while every prior
    version, source, actor, and correction link remains preserved.

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

The Product API also stores per-resident notification/awareness preferences
and authorized resident-memory administration. Preferences control future
delivery only; real notification sending is later scope. Memory edits never
rewrite event history, numerical calibration, or safety policy. The resident
controls verification command is
`python3 -m backend.app.checkpoints.preferences_memory`.

The Product API now exposes the clinic-wide event queue with active-work
defaults, combined filters, caregiver-attention ordering, stable pagination,
resolved history, and tenant masking. A committed generated OpenAPI document
matches the running application, and the exact frontend composition is written
in `docs/PHASE_2_FRONTEND_API_HANDOFF.md`. The complete clinic handoff command
is `python3 -m backend.app.checkpoints.clinic_handoff`.

## What Rishit can build now

Rishit does not need to wait for the database, API, or hardware. He can
continue the complete mock-backed product flow and begin the selected real API
connection now.

He can build the real clinic dashboard and separate home experience against contract-valid mock data, including:

- room and resident status;
- active, away, limited, and unavailable monitoring states;
- calibration and recalibration states;
- event priority, recurrence, overdue state, and history;
- acknowledge, check, and resolve actions;
- feedback and resident-context editing;
- settings for awareness items and notifications;
- device assignment, health, last-seen, and honest per-source limitations.

The frontend keeps mock data behind its replaceable client/provider. The
published Product API can now replace selected clinic paths without redesigning
the screens.

The clinic caregiver experience is the first complete user journey. Rishit can build the full separate home experience on mocks now; Phase 7 later connects and validates that existing experience against mature monitoring data and family-safe permissions rather than rebuilding it.

## What Akshar builds next

The first durable Product API slice and Checkpoints A–D are implemented.
There is no hidden Phase 2 backend checkpoint left. Akshar can support Rishit's
`ApiMonitoringClient` connection without pausing independent backend progress.

The Phase 5 normalized-fixture backend is complete: quality and purpose gating,
personal baselines, anomaly/evidence revisions, deterministic fake-AI
interpretation and validation, disposition/event bridging, acknowledgment,
recurrence, learning controls, and the 24-scenario replay now pass their
backend gate. The replay explicitly selects eligible resident context for a
nonurgent AI request and proves anomaly, interpretation, disposition, bridge,
and caregiver-event lineage across a repository restart. Akshar can support
Rishit's frontend convergence and prepare the separate Phase 6 simulated
edge-telemetry ingestion path. Phase 6, a real LLM provider, and real device
data are not implemented by this milestone.

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
- Routine context can reduce avoidable non-urgent alerts, but never suppresses urgent physical evidence.
- Acknowledgment quiets duplicate attention; it does not falsely end an active anomaly.
- AI interprets meaningful evidence, while deterministic policy owns the final disposition.

## Source-of-truth handoff

- Standalone founder/reviewer backend status:
  `docs/COFOUNDER_BACKEND_REVIEW.md`
- Phase status, review gates, and team cadence: `docs/PHASE_GATES.md`
- Product behavior: `docs/PRD.md`
- System boundaries: `docs/ARCHITECTURE.md`
- Shared frontend/backend/hardware language: `docs/DATA_CONTRACT.md`
- Build order: `docs/BUILD_PLAN.md`
- Ownership: `docs/TEAM_OWNERSHIP.md`
- Checkpoint A evidence: `docs/PHASE_2_CHECKPOINT_A_REVIEW.md`
- Checkpoint B evidence: `docs/PHASE_2_CHECKPOINT_B_REVIEW.md`
- Checkpoint C evidence: `docs/PHASE_2_CHECKPOINT_C_REVIEW.md`
- Checkpoint D evidence: `docs/PHASE_2_CHECKPOINT_D_REVIEW.md`
- Frontend API map: `docs/PHASE_2_FRONTEND_API_HANDOFF.md`
- Phase 5 backend intelligence evidence: `docs/PHASE_5_BACKEND_REVIEW.md`
- Monitoring intelligence evaluation workflow: `docs/MONITORING_INTELLIGENCE_LAB.md`
- Generated Product API: `docs/openapi/product-api-v1.json`
