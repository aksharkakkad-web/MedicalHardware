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
| Phase 2 — first complete event experience | **Ready to start** | Backend makes the product flow durable and accessible; Rishit builds the actual clinic experience on contract-valid mocks; hardware defines product-facing device states. |

### Why Phase 2 is ready

- The core V1 product decisions are written and merged.
- The shared frontend/backend/hardware language is already documented.
- The toy-data flow has automated coverage and is a repeatable shared scenario.
- Team ownership is clear, and there is no competing active work.

### What Phase 2 does **not** claim

The database, real API, real frontend app, sensor ingestion, hardware intelligence, authentication, notifications, clinical validation, and deployment are not finished. They are the work ahead, not missing prerequisites for starting Phase 2.

## The phase-by-phase roadmap

| Phase | Shared outcome | Frontend / Rishit | Backend / Akshar | Hardware | Exit checkpoint |
| --- | --- | --- | --- | --- | --- |
| 1. Product-logic foundation | Agree on the product's core behavior and prove it with toy data. | Product flow and mock direction defined. | Monitoring, calibration, event, feedback, and memory rules proved in toy scenarios. | Device responsibilities and future boundary defined. | **Complete:** everyone uses the same meaning for resident status and events. |
| 2. First complete event experience | Make one caregiver event journey real enough to build against. | Clinic resident overview, event list/detail, priority, uncertainty, acknowledge/check/resolve, and feedback flows on mocks. | Durable room/resident/event/feedback history and the first Product API around the agreed journey. | Product-facing device states: online, offline, poor quality, buffering, retrying, assignment unavailable. | A caregiver can complete the same event journey in frontend mocks and backend rules without contradicting each other. |
| 3. First convergence on toy data | Connect the user experience to the real backend with no product redesign. | Replace one mock path with the real API; preserve mock mode and clear loading/failure states. | Serve the same contract, actions, audit history, and access boundaries. | Produce device-shaped toy messages at the agreed boundary. | The clinic experience runs on real backend toy data; the simulator can plug in later. |
| 4. Feedback and understandable explanations | Make events understandable and feedback useful. | Fast feedback, clear uncertainty, event explanation, resident-context editing. | Trusted feedback history, resident memory, recommendation/explanation support; deterministic warnings remain independent of AI. | Continue independent research and edge preparation. | A caregiver understands an event, records what happened, and sees that context preserved. |
| 5. Simulated monitoring | Let a realistic simulated room drive the product. | Scenario views for normal activity, device trouble, uncertainty, and recovery. | Ingest simulated signals; handle delay, duplicates, missing input, and connectivity changes. | Refine realistic simulated output and quality signals. | A room scenario becomes a meaningful product state or event without alert spam. |
| 6. Monitoring intelligence | Personalize responsibly and make confidence meaningful. | Show calibration, trends, confidence, degraded monitoring, and device health clearly. | Fusion, personal baselines, anomaly logic, confidence, and deterministic event decisions. | Validate sensor availability/quality reporting. | Normal situations stay mostly quiet; meaningful changes are understandable; weak data visibly lowers confidence. |
| 7. Home/family product | Add a separate, simpler family experience. | Home view focused on “are they okay?” rather than clinic workflow. | Appropriate, permissioned view of the same core information. | No new product dependency. | Clinic and family users receive safe, purpose-built views. |
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

**Shared story:** A caregiver sees a room/resident, opens a meaningful event, understands its priority and limitations, acknowledges/checks/resolves it, gives feedback, and can later see the preserved history and resident context.

**Backend scope:** persist the product state already proved with toy data and expose the first stable Product API around that story. Preserve audit history and the existing product invariants.

**Frontend scope:** build the clinic flow against contract-valid mocks behind a replaceable data client. Do not wait for the real API.

**Hardware scope:** define and test the product-facing device/monitoring states, not real clinical intelligence.

**Not in this phase:** real sensor fusion, anomaly intelligence, AI interpretation, notification delivery, family product, production deployment, or clinical claims.

**Phase 2 is complete when:** the three tracks can demonstrate the same caregiver story using the same contract; the backend preserves it, the frontend can render it, and the hardware boundary has a compatible status model.

## Source-of-truth map

- Current status and immediate handoff: `docs/CURRENT_STAGE.md`
- Product rules: `docs/PRD.md`
- System boundaries: `docs/ARCHITECTURE.md`
- Shared data/API/telemetry language: `docs/DATA_CONTRACT.md`
- Detailed build tasks: `docs/BUILD_PLAN.md`
- Ownership and integration boundaries: `docs/TEAM_OWNERSHIP.md`
- Plain-language founder roadmap: `docs/AKSHAR_START_HERE.md`
