# Team Ownership & Parallel Development

**Status:** Source of truth for human ownership and parallel coding boundaries
**Team:** Akshar + Rishit + Hardware/Firmware Engineer
**Goal:** All three owners should be able to work continuously with minimal file overlap, minimal waiting, and predictable integration.

---

## 1. Core Operating Model

The three owners work within stable system boundaries rather than taking turns by phase.

- **Akshar owns backend + intelligence.**
- **Rishit owns frontend + user-facing product experience.**
- **Hardware/Firmware Engineer owns the device + edge system.**
- **Shared contracts are the boundary between them.**
- All three work in parallel against the same documented contracts.

The milestone order in `BUILD_PLAN.md` describes dependencies and integration checkpoints. It does **not** mean one founder waits while the other completes a phase.

---

## 2. Akshar — Backend & Intelligence Owner

Akshar owns the system behind the product UI.

### Primary areas

```text
backend/
prompts/
evals/
```

### Responsibilities

- FastAPI backend and API design/implementation
- Postgres/Supabase data layer
- migrations and persistence
- tenant/facility/room/resident/device domain logic
- edge-telemetry ingestion
- device-to-room and room-to-resident assignment logic
- single-resident room ambiguity/confidence handling
- telemetry validation
- cross-sensor fusion
- personal baseline engine
- anomaly detection
- deterministic warning/event logic
- confidence and data-quality logic
- device-health logic
- event lifecycle backend
- LLM provider abstraction
- event interpretation/context retrieval
- resident memory backend
- feedback persistence and learning logic
- backend tests/integration tests
- monitoring/evaluation logic for backend intelligence

### Akshar does not normally edit

```text
apps/clinic-dashboard/
apps/home-app/
```

except for a deliberate handoff or a tiny integration fix agreed with the frontend owner.

---

## 3. Rishit — Frontend & Product Experience Owner

Rishit owns everything the caregiver or family directly experiences.

### Primary areas

```text
apps/clinic-dashboard/
apps/home-app/
simulator/
```

### Responsibilities

- design system and reusable UI components
- clinic dashboard
- resident overview/detail experiences
- alerts/events timeline and detail UX
- confidence, uncertainty, unavailable-data states
- room assignment and multi-person ambiguity states in the UI
- device-health UX
- calibration UX
- LLM interpretation presentation
- caregiver acknowledgment/check/resolve workflows
- AI-guided feedback conversation UX
- home/family app experience
- responsive/mobile behavior
- accessibility
- frontend state management
- frontend client/provider abstraction
- `MockMonitoringClient`
- `ApiMonitoringClient`
- contract-valid mock fixtures
- scenario simulator used to drive the product UI and end-to-end demos
- frontend unit/component tests
- browser/E2E tests

### Simulator boundary

Rishit owns **scenario generation and telemetry simulation**, not the real cloud intelligence.

The simulator may generate scenarios such as:

- normal resident state
- physiological deviation
- unusual movement
- fall-like/collapse-like sequence
- prolonged inactivity
- repetitive movement
- multi-person ambiguity
- missing/conflicting room assignment state
- device/sensor failure
- recurring normal routine
- recovery

The simulator must output the same versioned edge-telemetry contract used by real hardware. It must not duplicate the real baseline/anomaly/LLM logic.

### Rishit does not normally edit

```text
backend/
prompts/
evals/
```

except for a deliberate handoff or a tiny integration fix agreed with Akshar.

---

## 3A. Hardware/Firmware Engineer — Device & Edge Owner

The hardware/firmware engineer owns the physical sensing node and the lightweight processing required to produce usable, versioned device information.

### Primary areas

```text
firmware/
hardware bring-up and bench-test assets
sensor-specific edge adapters and fixtures
```

### Responsibilities

- radar, thermal, and Wi-Fi CSI hardware bring-up;
- firmware sensor acquisition and device control;
- per-sensor raw-to-usable conversion at the device boundary;
- lightweight invalid-data filtering, reduction, compression, and packaging;
- timestamps, sequence numbers, buffering, retry, and device connectivity;
- device and per-sensor health reporting;
- bounded raw/debug capture for development and calibration;
- mapping real hardware output into the same edge-telemetry contract used by simulation;
- hardware bench tests and documentation of real sensor limitations.

### Boundary

The hardware/firmware engineer does not own cloud fusion, personal baselines, anomaly/event decisions, AI interpretation, feedback learning, or frontend product behavior. Hardware discoveries should normally be handled inside the device/adapter boundary; shared product or contract changes require coordination.

---

## 4. Shared Areas

The following are shared and require coordination:

```text
docs/
shared contract/type package if created
OpenAPI / generated API types
repo-level CI/configuration
```

### Shared decisions

- product behavior
- domain/event semantics
- API/data contracts
- event lifecycle states
- severity/confidence meanings
- resident/room assignment semantics
- major architectural changes

### Contract rule

No owner changes a shared contract silently.

Before changing a shared schema/API/domain object:

1. state the reason for the change;
2. update `docs/DATA_CONTRACT.md`;
3. agree on the new contract;
4. assign **one person** to make the contract change;
5. update generated/backend/frontend types;
6. update fixtures/tests;
7. integrate both sides against the same version.

Contract changes should be relatively rare once implementation starts.

---

## 5. Parallel Development Pattern

All three owners should normally be active at the same time.

Example:

```text
RISHIT                                 AKSHAR                                HARDWARE/FIRMWARE

Build event-detail UI                 Build event API
using mock MonitoringEvent            returning MonitoringEvent
        │                                      │
        └──────── DATA CONTRACT ───────────────┘

Build feedback conversation           Build feedback persistence
using mock FeedbackRecord             + resident-memory update
        │                                      │
        └──────── DATA CONTRACT ───────────────┘

Build device-health UI                Build device-health backend
using mock DeviceHealthRecord         + API                                  Define device-health signals

Define product scenarios              Process simulated telemetry             Produce device-shaped test data
        │                                      │                                      │
        └──────────────────── EDGE TELEMETRY CONTRACT ────────────────────────────────┘
```

Integration should normally mean swapping:

```text
MockMonitoringClient
        ↓
ApiMonitoringClient
```

not rewriting the UI.

When hardware arrives, the hardware/firmware track replaces the simulated telemetry producer. That should not require rebuilding the backend intelligence or the frontend product flow.

---

## 6. Repository Ownership Map

| Area | Primary owner | Notes |
|---|---|---|
| `apps/clinic-dashboard/` | Rishit | Clinic product UI/UX |
| `apps/home-app/` | Rishit | Home/family UI/UX |
| `simulator/` | Rishit | Product scenarios + edge-telemetry simulation; coordinate sensor-specific fidelity with hardware owner |
| `backend/` | Akshar | APIs, DB, monitoring engine |
| `prompts/` | Akshar | LLM/feedback prompt assets |
| `evals/` | Akshar | Intelligence/evaluation harness; frontend E2E stays with Rishit |
| `docs/PRD.md` | Shared | Product source of truth |
| `docs/ARCHITECTURE.md` | Shared | Architecture source of truth |
| `docs/DATA_CONTRACT.md` | Shared | Contract source of truth; one editor at a time |
| `docs/BUILD_PLAN.md` | Shared | Execution plan |
| `docs/TEAM_OWNERSHIP.md` | Shared | Human ownership source of truth |
| repo-level CI/config | Shared | Coordinate when changing |
| `firmware/` and hardware bench assets | Hardware/Firmware Engineer | Device acquisition, edge preprocessing, transport, and hardware validation |

---

## 7. Git / Worktree Rules

Use short-lived branches/worktrees with clear ownership rather than both founders coding directly on the same branch.

Suggested naming:

```text
akshar/backend-<task>
cofounder/frontend-<task>
```

Coding agents create these branches automatically with:

```bash
scripts/start-work.sh backend "<task>"
scripts/start-work.sh frontend "<task>"
```

The helper only starts from clean `main` and refuses to duplicate an existing
branch. Founders normally describe the work; they do not need to run Git setup
commands themselves.

Rules:

- `main` should stay runnable/green.
- Keep changes scoped to owned directories whenever possible.
- Pull/rebase from `main` regularly so branches do not drift for weeks.
- Prefer small merges over giant long-lived branches.
- Do not mix unrelated frontend and backend refactors in one change.
- Shared-contract edits should be isolated and integrated first when both sides depend on them.
- If both founders need the same shared file, explicitly choose one editor for that change.

The goal is not literally zero merges; the goal is that merges are routine because file ownership barely overlaps.

---

## 8. Codex/Subagent Rules by Founder

Each founder may use multiple Codex agents/worktrees inside their own lane.

### Akshar examples

Parallel when independent:

- API/database agent
- anomaly/baseline agent
- LLM/context agent
- backend verifier/eval agent

Avoid parallel agents editing the same schema or central monitoring module.

### Rishit examples

Parallel when independent:

- clinic-dashboard agent
- home-app agent
- design-system agent
- simulator/scenario agent
- frontend verifier/E2E agent

Avoid parallel agents editing the same shared component or frontend contract layer.

### Reviewer rule

A reviewer/verifier agent should check:

- contract compliance
- tests
- product requirements
- architecture boundaries
- whether a change crossed human ownership without reason

---

## 9. Handoff Definition

A feature is ready to connect when both sides satisfy the same contract.

Example event feature:

**Rishit ready:**
- event UI works against mock contract;
- loading/error/low-confidence states work;
- frontend tests pass.

**Akshar ready:**
- event API returns contract-valid data;
- persistence/lifecycle work;
- backend tests pass.

**Integration:**
- switch client/provider to real API;
- run E2E flow;
- fix only genuine integration gaps;
- do not redesign either side unnecessarily.

---

## 10. Balance Principle

Workload is balanced by owning complete problem domains, not by counting files or commits.

**Akshar:** complexity is concentrated in data, algorithms, APIs, persistence, AI, and system reliability.

**Rishit:** complexity is concentrated in two polished product surfaces, interaction design, frontend architecture, mocks/simulator, state handling, responsiveness, accessibility, and E2E quality.

**Hardware/Firmware Engineer:** complexity is concentrated in physical sensor behavior, device reliability, signal acquisition, edge reduction, buffering/transport, real-world quality limits, and repeatable hardware validation.

If one side becomes materially blocked or overloaded, rebalance a self-contained module rather than creating shared ownership of everything.
