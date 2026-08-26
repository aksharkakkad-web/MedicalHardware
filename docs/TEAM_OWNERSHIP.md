# Team Ownership & Parallel Development

**Status:** Source of truth for human ownership and parallel coding boundaries
**Team:** Akshar + Frontend/Product Cofounder
**Goal:** Both founders should be able to code continuously with minimal file overlap, minimal waiting, and predictable integration.

---

## 1. Core Operating Model

The two founders own stable system boundaries rather than taking turns by phase.

- **Akshar owns backend + intelligence.**
- **Cofounder owns frontend + product experience.**
- **Shared contracts are the boundary between them.**
- Both work in parallel against the same documented contracts.

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
- RFID tag-to-resident mapping and identity confidence
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

## 3. Cofounder — Frontend & Product Experience Owner

The frontend/product cofounder owns everything the caregiver or family directly experiences.

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
- RFID identity/attribution states in the UI
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

The cofounder owns **scenario generation and telemetry simulation**, not the real cloud intelligence.

The simulator may generate scenarios such as:

- normal resident state
- physiological deviation
- unusual movement
- fall-like/collapse-like sequence
- prolonged inactivity
- repetitive movement
- multi-person ambiguity
- RFID missing/ambiguous/multiple-tag state
- device/sensor failure
- recurring normal routine
- recovery

The simulator must output the same versioned edge-telemetry contract used by real hardware. It must not duplicate the real baseline/anomaly/LLM logic.

### Cofounder does not normally edit

```text
backend/
prompts/
evals/
```

except for a deliberate handoff or a tiny integration fix agreed with Akshar.

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
- resident identity semantics
- major architectural changes

### Contract rule

Neither founder changes a shared contract silently.

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

Both founders should normally be active at the same time.

Example:

```text
COFOUNDER                              AKSHAR

Build event-detail UI                 Build event API
using mock MonitoringEvent            returning MonitoringEvent
        │                                      │
        └──────── DATA CONTRACT ───────────────┘

Build feedback conversation           Build feedback persistence
using mock FeedbackRecord             + resident-memory update
        │                                      │
        └──────── DATA CONTRACT ───────────────┘

Build device-health UI                Build device-health backend
using mock DeviceHealthRecord         + API
```

Integration should normally mean swapping:

```text
MockMonitoringClient
        ↓
ApiMonitoringClient
```

not rewriting the UI.

---

## 6. Repository Ownership Map

| Area | Primary owner | Notes |
|---|---|---|
| `apps/clinic-dashboard/` | Cofounder | Clinic product UI/UX |
| `apps/home-app/` | Cofounder | Home/family UI/UX |
| `simulator/` | Cofounder | Scenario + edge-telemetry simulation |
| `backend/` | Akshar | APIs, DB, monitoring engine |
| `prompts/` | Akshar | LLM/feedback prompt assets |
| `evals/` | Akshar | Intelligence/evaluation harness; frontend E2E stays with cofounder |
| `docs/PRD.md` | Shared | Product source of truth |
| `docs/ARCHITECTURE.md` | Shared | Architecture source of truth |
| `docs/DATA_CONTRACT.md` | Shared | Contract source of truth; one editor at a time |
| `docs/BUILD_PLAN.md` | Shared | Execution plan |
| `docs/TEAM_OWNERSHIP.md` | Shared | Human ownership source of truth |
| repo-level CI/config | Shared | Coordinate when changing |
| firmware/hardware | Hardware owner later | Separate from the two-person software split |

---

## 7. Git / Worktree Rules

Use short-lived branches/worktrees with clear ownership rather than both founders coding directly on the same branch.

Suggested naming:

```text
akshar/<backend-task>
cofounder/<frontend-task>
```

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

### Cofounder examples

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

**Cofounder ready:**
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

**Cofounder:** complexity is concentrated in two polished product surfaces, interaction design, frontend architecture, mocks/simulator, state handling, responsiveness, accessibility, and E2E quality.

If one side becomes materially blocked or overloaded, rebalance a self-contained module rather than creating shared ownership of everything.
