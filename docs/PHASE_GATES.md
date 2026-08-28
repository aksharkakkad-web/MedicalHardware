# Project Phase Gates

**Purpose:** This is the team's one-page operating dashboard. It answers: where are we, what is each person building now, what proves a phase is complete, and when do we move on?

For detailed product rules, use `docs/PRD.md`. For detailed build tasks, use `docs/BUILD_PLAN.md`. This document does not replace either one.

## How we run every phase

```text
1. Start: agree on one goal, one end-to-end story, and clear non-goals.
2. Build: each owner works independently inside their lane.
3. Check: automated tests and the agreed story prove the behavior.
4. Review: founders see a plain-language walkthrough and make product decisions.
5. Record: update the relevant source-of-truth docs and merge the phase work.
6. Advance: explicitly mark the phase complete, then start the next phase.
```

All three tracks work in parallel. A phase is not a rule that Akshar, Rishit, or the hardware engineer must wait for one another. A phase closes only when its **shared checkpoint** is met; preparation for a later phase may continue as long as it does not change an agreed contract.

## Current status

| Current gate | Status | What this means |
| --- | --- | --- |
| Phase 1 — product-logic foundation | **Complete** | The agreed monitoring, calibration, event, feedback, recurrence, and resident-memory behavior runs with deterministic toy data. |
| Phase 2 — first complete event experience | **In progress** | The durable event slice and backend Checkpoints A–D are complete. Rishit's remaining clinic/home mock experiences, the real-client connection, and hardware's real device work remain open. |
| Phase 5 — monitoring intelligence | **Backend active in parallel** | Research and product logic are locked. Akshar is building the normalized-fixture intelligence path while Phase 2 frontend convergence proceeds independently. |

### Why Phase 2 is ready

- The core V1 product decisions are written and merged.
- The shared frontend/backend/hardware language is already documented.
- The toy-data flow has automated coverage and is a repeatable shared scenario.
- Team ownership is clear, and there is no competing active work.

### Completed backend checkpoints

The synthetic caregiver story now preserves its room/resident assignment,
event action history, trusted feedback, resident memory, idempotency records,
and audit history across an application restart. The first Product API read and
caregiver-action paths are frozen in `docs/DATA_CONTRACT.md`.

Checkpoint A additionally preserves active/away/return/possible-multi-person
awareness, current resident status, calibration versions, and selective setup
changes across restart. Its evidence is in
`docs/PHASE_2_CHECKPOINT_A_REVIEW.md`. Device assignment/health evidence is in
`docs/PHASE_2_CHECKPOINT_B_REVIEW.md`. Preference/resident-memory evidence is
in `docs/PHASE_2_CHECKPOINT_C_REVIEW.md`. The final clinic queue/OpenAPI handoff
is in `docs/PHASE_2_CHECKPOINT_D_REVIEW.md`. The Phase 2 backend runway is
complete; frontend connection is next.

### What Phase 2 does **not** claim

The complete frontend experiences, real hardware implementation, later
database/API phases, production authentication, sensor ingestion,
hardware intelligence, notifications, clinical validation, and deployment are
not finished. They remain open work, so the overall Phase 2 gate stays
**In progress**.

## The phase-by-phase roadmap

| Phase | Shared outcome | Frontend / Rishit | Backend / Akshar | Hardware | Exit checkpoint |
| --- | --- | --- | --- | --- | --- |
| 1. Product-logic foundation | Agree on the product's core behavior and prove it with toy data. | Product flow and mock direction defined. | Monitoring, calibration, event, feedback, and memory rules proved in toy scenarios. | Device responsibilities and future boundary defined. | **Complete:** everyone uses the same meaning for resident status and events. |
| 2. First complete event experience | Make the clinic and home user experiences real enough to build against. | Build the full clinic and separate home experiences on contract-valid mocks: clinic operations stay clinic-only, while the home experience uses family-safe language and simple feedback. | **Event slice + Checkpoints A–D complete:** durable events, feedback, resident status/awareness, calibration, setup history, device assignment/health, resident delivery preferences, correctable memory, clinic event queue, and generated API handoff. **Next:** support frontend real-client convergence. | **Product-facing device state contract complete:** online, offline, degraded, buffering, retrying, assignment unavailable, and honest missing data. Real device production remains open. | Clinic and home mock experiences complete their agreed stories without contradicting backend rules or each other. |
| 3. First convergence on toy data | Connect the user experience to the real backend with no product redesign. | Replace one mock path with the real API; preserve mock mode and clear loading/failure states. | Serve the same contract, actions, audit history, and access boundaries. | Produce device-shaped toy messages at the agreed boundary. | The clinic experience runs on real backend toy data; the simulator can plug in later. |
| 4. Feedback and understandable explanations | Make events understandable and feedback useful. | Fast feedback, clear uncertainty, event explanation, resident-context editing. | Trusted feedback history, resident memory, recommendation/explanation support; deterministic warnings remain independent of AI. | Continue independent research and edge preparation. | A caregiver understands an event, records what happened, and sees that context preserved. |
| 5. Monitoring intelligence on normalized simulated data | Personalize responsibly and make confidence meaningful before edge transport is introduced. | Show calibration, trends, confidence, degraded monitoring, and device health clearly. | Use normalized simulated fixtures for quality, personal baselines, anomaly episodes, rich evidence, selective situation-specific AI interpretation, and deterministic event disposition. Strong urgent evidence bypasses AI delay. | Validate sensor availability/quality reporting. | Flexible normal routines stay mostly quiet; meaningful simulated changes create understandable events, urgent evidence surfaces without AI dependency, and weak data visibly lowers confidence. |
| 6. Simulated telemetry and ingestion | Drive the established monitoring intelligence through the same edge-telemetry boundary future hardware will use. | Scenario views for normal activity, device trouble, uncertainty, and recovery; show the resulting event journey. | Ingest, persist, validate, deduplicate, and replay simulated signals, then pass them through the Phase 5 monitoring/event engine; handle delay, missing input, and connectivity changes. | Refine realistic simulated output and quality signals. | A room scenario safely travels from simulated telemetry through the established event engine into the product UI; device/transport quality remains honest. |
| 7. Home/family product | Connect and validate the existing separate home experience against mature monitoring data. | Replace the home mock client with a family-safe real-data client; validate language and permissions without copying clinic operations or rebuilding the core screens. | Provide an appropriate, permissioned view of the same core information. | No new product dependency. | The existing home experience works safely on mature data while clinic and family users receive different purpose-built views. |
| 8. Evaluation and learning | Measure whether the product is useful, not just functional. | Test comprehension, effort, and alert-fatigue risks. | Replay scenarios and measure missed events, false alerts, response, confidence, and personalization. | Contribute hardware quality evidence. | Versions can be compared with evidence rather than impressions. |
| 9. Real hardware | Replace the simulator without changing the product story. | Add setup, connectivity, health, and calibration experiences learned from hardware testing. | Ingest real device telemetry and preserve existing event/product behavior. | Bring up radar, thermal, and Wi-Fi CSI; supply real compact telemetry. | Real hardware feeds the established flow without rewriting frontend or event logic. |
| 10. Pilot readiness | Prepare a controlled, supportable real-world pilot. | Finalize operational UX and support flows. | Reliability, access, security, retention, observability, and operational controls. | Device reliability and deployment validation. | Separate privacy, safety, compliance, and pilot-readiness review passes before real clinical use. |

## Required phase review

Before a phase is marked complete, review these questions together:

1. Does the agreed user story work from start to finish?
2. Does uncertain or missing data behave honestly?
3. Are frontend, backend, and hardware boundaries still compatible?
4. What changed in the product decisions, and which source-of-truth document records it?
5. What is explicitly deferred to the next phase?
6. Do the automated checks and the product walkthrough both pass?

The output is one of three outcomes: **approved and advance**, **revise this phase**, or **defer a decision with an owner and a later phase**.

## Phase 2 kickoff brief

**Goal:** Make the first caregiver event journey durable and connectable while Rishit builds the real clinic flow with mock data.

**Clinic story:** A caregiver sees a room/resident, opens a meaningful event, understands its priority and limitations, acknowledges/checks/resolves it, gives feedback, and can later see the preserved history and resident context.

**Home story:** A family member sees a loved one's simple status and trends, reads event information in family-safe language, and can provide simple routine feedback. The home experience does not expose clinic acknowledgement, checking, resolution, or other operations.

**Backend scope:** persist the product state already proved with toy data and expose the first stable Product API around that story. Preserve audit history and the existing product invariants.

**Frontend scope:** build the full clinic flow and the full, separate home experience against contract-valid mocks behind replaceable data clients. Do not wait for the real API. Phase 7 connects and validates that existing home experience against mature real monitoring data; it does not rebuild it.

**Hardware scope:** define and test the product-facing device/monitoring states, not real clinical intelligence.

**Not in this phase:** real sensor fusion, anomaly intelligence, AI interpretation, notification delivery, mature family-specific real-data permissions, production deployment, or clinical claims.

**Phase 2 is complete when:** the clinic and home stories each work on their own contract-valid mock client; the backend preserves the underlying product state; and the hardware boundary has a compatible status model.

## Source-of-truth map

- Current status and immediate handoff: `docs/CURRENT_STAGE.md`
- Product rules: `docs/PRD.md`
- System boundaries: `docs/ARCHITECTURE.md`
- Shared data/API/telemetry language: `docs/DATA_CONTRACT.md`
- Detailed build tasks: `docs/BUILD_PLAN.md`
- Ownership and integration boundaries: `docs/TEAM_OWNERSHIP.md`
- Plain-language founder roadmap: `docs/AKSHAR_START_HERE.md`
