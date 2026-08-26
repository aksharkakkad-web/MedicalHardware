# Contactless Adaptive Care Platform — Build Plan

**Status:** Execution plan
**Strategy:** Contract-first, UI/UX-first, back-to-front, simulator-backed
**Version:** 1.5

---

## 1. Build Philosophy

We will build from the user experience backward toward the physical device while keeping stable contracts between layers.

The first visible product should be the **real clinic/home frontend running on contract-valid mock data**, not disposable design-only mockups. Backend and sensor functionality will then replace mock providers behind the same interfaces.

The hardware parts are already ordered. Software work should not wait for them.

### Core rules

> **Mock provider and real API are interchangeable data sources at the frontend boundary.**

> **Real hardware and simulator are interchangeable producers of the same compact edge-telemetry contract at the ingestion boundary.**

The implementation should always prefer one complete vertical slice over many disconnected half-built systems.

---

## 2. Source of Truth

Before coding any feature, read:

1. `docs/PRD.md` — what the product must do
2. `docs/ARCHITECTURE.md` — how layers are separated
3. `docs/DATA_CONTRACT.md` — exact domain/message semantics
4. `docs/TEAM_OWNERSHIP.md` — founder ownership and parallel-development boundaries
5. this file — build sequence and acceptance criteria

`AGENTS.md` is the map and operating rules, not the encyclopedia.

---


## 3. Human Parallel-Development Model

Milestones in this document describe dependency order and integration checkpoints. They are **not** a rule that one founder waits while the other completes a phase.

Primary ownership:

- **Akshar — backend + intelligence:** `backend/`, `prompts/`, backend intelligence/evals.
- **Rishit — frontend + product + scenario simulator:** `apps/clinic-dashboard/`, `apps/home-app/`, `simulator/`.
- **Hardware/Firmware Engineer — device + edge system:** `firmware/` and hardware bench-test assets.
- **Shared — contracts/docs:** coordinate and assign one editor at a time.

All three owners should normally work concurrently against the same frozen contracts. The frontend should progress against mocks, the backend against the real API/domain implementation, and the hardware track against the edge-telemetry boundary and bring-up plan.

Example:

```text
Rishit                                 Akshar                              Hardware/Firmware
Event UI on mock contract       <->   Event API on same contract
Feedback UX on mock contract    <->   Feedback persistence/memory
Device-health UI                <->   Device-health service/API      <-> Device health + telemetry producer
```

See `docs/TEAM_OWNERSHIP.md` for exact directory ownership, Git/worktree rules, Codex/subagent guidance, and handoff criteria.

---

## 4. Recommended Codex Workflow

Use Codex tasks like well-written GitHub issues:

- one clear objective;
- exact files/modules when known;
- constraints;
- acceptance criteria;
- tests to run;
- explicit non-goals.

Use parallel agents only when work has clear file/module ownership.

### Suggested agent roles

**Planning / Architect Agent**
- reads all docs;
- turns a milestone into implementation tasks;
- does not code unless asked.

**Frontend Agent (normally run by Rishit)**
- owns clinic/home UI work, frontend client/provider layer, and product-facing simulator scenarios;
- consumes published API/contracts;
- does not invent backend schemas.

**Backend / Data Agent (normally run by Akshar)**
- owns FastAPI, Postgres models/migrations, ingestion/domain/event APIs;
- follows `DATA_CONTRACT.md`.

**Monitoring Intelligence Agent (normally run by Akshar)**
- owns cloud telemetry validation, sensor fusion, baseline, anomaly/event logic, confidence, and backend eval fixtures;
- must not add unsupported medical thresholds.

**Scenario Simulator Agent (normally run by Rishit)**
- owns contract-valid edge-telemetry scenarios used by mock UI and end-to-end demos;
- does not duplicate production baseline/anomaly/LLM logic.

**AI Agent (normally run by Akshar)**
- owns LLM interfaces, structured outputs, context builder, feedback backend, and resident-memory updater;
- does not control deterministic event creation.

**Reviewer / Verifier Agent**
- reviews against docs;
- runs tests/evals;
- looks for contract drift, safety-path violations, unhandled failures, and fabricated data.

### Parallelism rule

Good parallel pair:

- Frontend dashboard working from mocked API fixtures
- Backend event API implementing the same published contract

Bad parallel pair:

- two agents independently editing the shared event schema

Use separate Codex worktrees/threads for independent tasks, then integrate through the shared contracts.

---

## 5. Milestone 0 — Repository Bootstrap

### Goal

Create a boring, predictable repo Codex can navigate.

### Deliverables

- root `AGENTS.md`
- `docs/` source-of-truth files
- `apps/clinic-dashboard`
- `apps/home-app`
- `backend/`
- `firmware/`
- `simulator/`
- `prompts/`
- `evals/`
- `.env.example`
- CI skeleton
- formatting/lint/test configuration

### Recommended defaults

Frontend:

- Next.js
- TypeScript
- pnpm

Backend:

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy + Alembic
- pytest
- Ruff

Database:

- Postgres / Supabase

### Acceptance criteria

- frontend dev server boots;
- backend health endpoint responds;
- one backend test passes;
- frontend lint/typecheck/build run;
- CI can execute basic checks;
- no secrets committed.

---

## 6. Milestone 1 — Shared Domain Contracts

### Goal

Turn `DATA_CONTRACT.md` into code before building major features.

### Deliverables

Backend Pydantic models for:

- EdgeTelemetryEnvelope
- DiagnosticRawEnvelope (optional/debug path)
- DeviceHeartbeat
- NormalizedObservation
- FusedFrame
- BaselineSnapshot
- AnomalyCandidate
- MonitoringEvent
- InterpretationInput/Output
- FeedbackRecord
- ResidentMemorySnapshot
- DeviceHealthRecord

Frontend TypeScript API types generated/shared from a stable API schema where practical.

### Acceptance criteria

- schema validation tests;
- invalid payload tests;
- OpenAPI docs generated;
- example fixtures parse cleanly;
- simulator fixtures use the same edge-telemetry envelope.

### Agent note

Only one agent owns shared contract edits at a time.

---

## 7. Milestone 2 — Production UI/UX on Mock Data

### Goal

Build both product surfaces as the **actual production UI/UX** before the sensor pipeline exists.

### Ownership

**Rishit owns this product track.** Akshar can simultaneously build backend/domain work against the same contracts; neither side waits for the other. They initially run against contract-valid mock clients and later switch to real APIs without a redesign.

### Clinic dashboard — production UI backed by mock client

Build:

- resident overview;
- normal/watch/high/critical-style visual priority states;
- resident detail;
- event list;
- event detail with objective evidence;
- interpretation section;
- confidence/data-quality section;
- device health section;
- room assignment and multi-person ambiguity status;
- acknowledge/check/resolve controls;
- feedback entry flow.

### Home app — production UI backed by mock client

Build:

- loved-one overview;
- simple current status;
- meaningful trend cards;
- event detail in family-friendly language;
- simple feedback/routine input;
- no clinic operations UI.

### Required mock scenarios

- normal resident;
- calibrating resident;
- unusual movement event;
- physiological deviation;
- unknown anomaly;
- low-confidence/multi-person event;
- valid one-resident room assignment;
- missing/conflicting room assignment;
- suspected multi-person presence;
- resident away and return;
- setup change and recalibration;
- recurring/linked event and overdue high-priority event;
- editable resident memory and notification preferences;
- device issue;
- LLM pending/unavailable;
- event acknowledged/checked/resolved;
- confirmed/false-positive/uncertain feedback.

### Acceptance criteria

- complete click-through with contract-valid fixture data;
- mock data is accessed through a typed mock client/provider, not imported ad hoc into UI components;
- acknowledge/check/resolve/feedback interactions work in mock mode;
- low-confidence/unavailable state visibly handled;
- LLM unavailable state visibly handled;
- unknown anomaly state is understandable;
- clinic and home UX remain separate;
- replacing `MockMonitoringClient` with `ApiMonitoringClient` should not require component redesign.

---

## 8. Milestone 3 — Database + Event Backend

**Ownership:** **Akshar owns this backend track.** Frontend work continues in parallel against mocks/contracts until APIs are ready.


### Goal

Implement durable domain APIs behind the exact contracts already exercised by the mock-backed frontends, then switch the frontend client from mock to API.

### Deliverables

- tenant/location/room/resident/device tables;
- event tables;
- interpretation tables;
- feedback tables;
- device health;
- baseline/memory version records;
- migrations;
- CRUD/query APIs needed by UIs;
- event lifecycle state transitions;
- event episode grouping, recurrence links, overdue state, and priority history;
- resident presence/monitoring awareness timeline;
- monitoring-setup versions and recalibration reasons;
- administrator notification preferences;
- audit-friendly timestamps/actor fields.

### Acceptance criteria

- clinic UI switches from mock client to real API client without redesign;
- event lifecycle persists;
- home UI switches to shared domain data through home-specific API/view without redesign;
- tenant isolation tests;
- transition validation prevents invalid event state jumps.

---

## 9. Milestone 4 — LLM Interpretation Layer

### Goal

Make an existing structured event understandable without giving the LLM authority over event creation.

### Deliverables

- provider-neutral LLM interface;
- `prompts/event_interpreter.md`;
- context builder;
- structured output schema validation;
- retry/failure handling;
- interpretation persistence;
- model/prompt version capture;
- `unknown`/uncertain path.

### Acceptance criteria

- given a test event + resident context, returns valid structured interpretation;
- no raw sensor arrays are sent to the LLM;
- invalid LLM output is rejected/retried safely;
- LLM outage leaves event visible;
- deterministic event priority cannot be lowered/deleted by interpreter.

---

## 10. Milestone 5 — Feedback Agent + Resident Memory

### Goal

Close the user feedback loop before real sensors exist.

### Deliverables

- `prompts/feedback_agent.md`;
- outcome buttons: confirmed / false positive / uncertain;
- one/two follow-up question flow;
- structured feedback persistence;
- actor confidence/provenance;
- `prompts/resident_memory_updater.md`;
- versioned resident memory;
- relevant-memory retrieval for future interpretation;
- operator memory review, correction, and retirement with audit history.

### Acceptance criteria

- feedback takes only a few interactions;
- previous similar feedback can be retrieved for a later event;
- memory update is auditable;
- authorized operators can correct an inaccurate routine without deleting history;
- feedback never directly edits warning thresholds.

---

## 11. Milestone 6 — Anomaly/Event Engine on Normalized Simulated Data

### Goal

Build the numerical logic behind events without waiting for real edge firmware/preprocessors.

### Deliverables

- normalized fixture generator;
- baseline engine;
- general anomaly engine;
- configurable warning-policy engine;
- event creation/deduplication;
- confidence/data-quality inputs;
- device issue event path.

### Initial algorithms

Use simple transparent methods first:

- rolling statistics;
- change detection;
- deviation from personal baseline;
- duration/rate-of-change;
- cross-feature agreement;
- quality gating.

Do not prematurely build a trained event classifier.

### Acceptance criteria

- normal scenario produces low event rate;
- scripted anomaly produces event;
- clearly unusual but unclassified scenario can produce `unknown_anomaly`;
- low-quality data can suppress/qualify derived features without inventing values;
- warning-policy demo rules are explicitly synthetic/test-only;
- baseline versions are stored;
- calibration behavior is exercised across `new`, `calibrating`, `partial`, and `established`;
- away, possible-multi-person, poor-quality, and unresolved-event windows do not update the baseline;
- setup changes return affected baseline dimensions to calibration while preserving resident memory;

---

## 12. Milestone 7 — Sensor Fusion Layer

### Goal

Allow radar, thermal, and CSI normalized observations to contribute independently to the fused state of the resident assigned to a monitored room.

### Deliverables

- time-window alignment;
- modality presence tracking;
- sensor agreement score;
- multi-person/ambiguity state;
- missing-modality degradation;
- fused features with quality;
- fusion versioning.

### Acceptance criteria

- radar-only, thermal-only, CSI-only and combined sensing fixtures all process;
- valid and missing/conflicting room-resident assignments process safely;
- fusion does not crash when one source is missing;
- contradictory modalities lower confidence;
- multi-person test case lowers confidence or marks resident-specific output unavailable without guessing attribution.

---

## 13. Milestone 8 — Edge Telemetry Simulator + Ingestion

### Goal

Exercise the same compact edge-telemetry boundary the real ESP32 will use.

### Simulator scenarios

At minimum:

- normal rest;
- normal movement;
- physiological deviation;
- unusual movement;
- prolonged inactivity;
- fall-like sequence;
- collapse-like sequence;
- repetitive movement;
- multi-person/interference;
- resident away and return;
- monitoring setup change/recalibration;
- radar missing/noisy;
- thermal missing/noisy;
- CSI missing/noisy;
- device network outage/retry;
- recurring routine;
- unknown/unclassified anomaly;
- valid room/resident assignment;
- missing/conflicting room/resident assignment;
- recovery;
- related event recurrence inside and outside the configured episode gap.

### Deliverables

- edge-telemetry generator for radar, thermal, and CSI;
- ingestion endpoint;
- idempotency/deduplication;
- processed telemetry persistence;
- optional bounded diagnostic-raw fixture path;
- processing dispatch;
- heartbeat/last-seen;
- local simulator replay controls.

### Acceptance criteria

- duplicate packets do not double-process;
- network retry scenario is safe;
- ground-truth scenario label is kept outside production payload;
- end-to-end simulator event appears in UI;
- stored telemetry/event window can be replayed; diagnostic raw windows can be replayed when captured.

---

## 14. Milestone 9 — Edge Preprocessor + Cloud Normalizer Boundaries

### Goal

Create the edge-preprocessor and cloud-normalizer boundaries now, then fill in real hardware math as sensors arrive.

### Modules

Edge/firmware:
- radar preprocessor;
- thermal preprocessor;
- CSI preprocessor;

Cloud:
- radar telemetry normalizer;
- thermal telemetry normalizer;
- CSI telemetry normalizer;
- room/resident assignment adapter;
- optional medical accessory normalizers.

### Until hardware arrives

Use simulated edge-telemetry formats and placeholder-but-realistic edge preprocessing outputs.

### When hardware arrives

Only firmware/edge adapters and source normalizers should need hardware-specific changes.

### Acceptance criteria

- no vendor-specific payload parsing leaks outside firmware/edge adapter modules;
- edge outputs match EdgeTelemetryEnvelope;
- cloud normalizer outputs match NormalizedObservation contract;
- edge-preprocessor and normalizer versions are recorded;
- quality/unavailable states are supported.

---

## 15. Milestone 10 — Evaluation Harness

### Goal

Make system quality measurable before claiming it works.

### Deliverables

- scenario ground-truth store;
- replay runner;
- metric computation;
- experiment/version comparison;
- report output.

### Metrics

- recall;
- precision;
- false events per simulated monitored-day;
- detection latency;
- confidence calibration;
- modality ablation: radar vs thermal vs CSI vs fusion;
- room-assignment validity and multi-person ambiguity rate;
- global baseline vs personal baseline;
- before/after feedback personalization;
- LLM output validity/usefulness;
- device-health detection.

### Acceptance criteria

- one command replays the scenario suite;
- results are reproducible by version;
- regression thresholds can later be added to CI.

---

## 16. Milestone 11 — Real Hardware Integration

### Goal

Replace simulator producer with the real ESP32 without changing product/domain layers.

### Hardware discovery checklist

At integration time, document:

- actual radar output/raw access and local feature conversion;
- thermal framing/refresh and local reduction strategy;
- CSI capture format/rate and local feature/compression strategy;
- network bandwidth after edge preprocessing;
- device clock/time behavior;
- multi-person/interference behavior in nominally single-resident rooms;
- actual firmware edge-telemetry mapping;
- optional diagnostic raw-capture limits;
- buffering limits;
- room placement constraints.

### Work

- implement real firmware sensor drivers/preprocessors;
- map firmware packets into EdgeTelemetryEnvelope;
- implement device-to-room and room-to-resident assignment validation;
- calibrate edge/cloud quality logic;
- compare sensor-derived values against safe reference data;
- update simulator to resemble real signal characteristics.

### Acceptance criteria

- real hardware produces the same domain objects as simulator;
- UI/feedback/LLM stack requires no architectural rewrite;
- hardware-specific failures show correctly.

---

## 17. Milestone 12 — Optional Accessory Integrations

Only after core system works.

Potential adapters:

- SpO₂;
- BP cuff;
- future validated sensor.

Accessory rule:

> Add it only if it contributes new useful information or solves a proven failure mode.

---

## 18. Customer Discovery Track — Runs in Parallel

Engineering does not wait for market selection.

Maintain a structured interview log outside product code.

Learn:

- buyer;
- user;
- top pain;
- current alternative;
- required detections;
- acceptable false-alert rate;
- integration barriers;
- price expectations;
- pilot willingness.

Customer discovery may change product priority, not core architecture unless evidence demands it.

---

## 19. Research Track — Runs in Parallel

High-value experiments once data exists:

1. Does fusion beat each individual modality?
2. Do personal baselines improve detection versus generic thresholds?
3. Does caregiver/family feedback reduce false positives while preserving recall?
4. How well calibrated is system confidence?
5. Which sensor combinations contribute most to which event families?
6. Can specific cardiac/respiratory/event patterns be validated against reference measurements?

Do not claim diagnostic capability before validation.

---

## 20. Codex Task Template

Use this template for implementation tasks:

```text
Objective
<one concrete outcome>

Read first
- docs/PRD.md
- docs/ARCHITECTURE.md
- docs/DATA_CONTRACT.md
- docs/TEAM_OWNERSHIP.md
- relevant section of docs/BUILD_PLAN.md

Scope
- files/modules this task owns

Requirements
- specific behavior

Non-goals
- what not to build/change

Acceptance criteria
- observable pass/fail bullets

Verification
- commands/tests/evals to run

Documentation
- update source-of-truth docs if a contract/architecture decision changes
```

---

## 21. Agent Integration Rules

Before merging an agent's work:

- review diff;
- confirm no architecture boundary drift;
- run relevant tests;
- run type/lint/build checks;
- ensure schemas/docs remain synchronized;
- ensure no real PHI/secrets are present;
- ensure simulator/evals are updated when behavior changes.

Use reviewer/verifier agents for larger changes.

For complicated design choices, generating multiple plans/solutions and selecting the best is preferred over committing to the first plausible implementation.

---

## 22. Definition of Planning Complete

Planning is complete when:

- these docs are committed;
- repo is bootstrapped;
- contracts compile/validate;
- first Codex milestone is broken into issue-sized tasks.

After that, product brainstorming should not block implementation. New ideas go into backlog unless testing/customer evidence requires an architectural change.
