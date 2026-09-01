# Multi-Agent Monitoring Interpretation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace one-shot advisory interpretation with a provider-neutral three-stage AI pipeline in which a recall router proposes possibilities, selected specialists investigate in parallel, and a final integrator/reviewer owns operational severity and recommended action.

**Architecture:** Reuse the existing anomaly detector, evidence packet, event lifecycle, feedback, and resident-memory foundations. Add typed stage contracts, versioned skills, a checkpointable orchestrator, structured Gemini stage calls, deterministic grounding validation, and a trusted final-analysis bridge. Deterministic code detects anomalies and enforces lifecycle mechanics; it does not impose a severity floor on a valid final AI decision.

**Tech Stack:** Python 3.12+, frozen dataclasses and protocols, `concurrent.futures`, existing FastAPI/SQLAlchemy/Pydantic stack, pytest, Gemini REST structured JSON.

**Spec:** `docs/superpowers/specs/2026-09-01-multi-agent-monitoring-interpretation-design.md`

## Global Constraints

- V1 monitors one assigned resident per room and never guesses identity during multi-person ambiguity.
- The system does not diagnose medical conditions or invent clinical thresholds.
- Only bounded evidence, relevant resident context, and exact evidence references may enter AI calls.
- The recall router maximizes plausible coverage but does not set final severity or action.
- Selected specialists run independently and concurrently; they do not see each other's outputs.
- The final integrator/reviewer combines evidence and may preserve multiple credible explanations.
- `observe` remains valid regardless of numerical anomaly strength.
- Deterministic validation checks structure, provenance, and grounding only; it does not reinterpret the case.
- An unavailable or invalid AI result never makes an anomaly disappear; it becomes pending or staff-review-needed.
- Raw model chain-of-thought is neither requested nor persisted.
- Feedback and resident-memory updates remain separate, authorized, versioned post-event flows.
- Existing frontend files remain in Rishit's ownership; this change publishes backend/data contracts for convergence.

---

### Task 1: Align product and shared contracts with the approved ownership model

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/PRD.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DATA_CONTRACT.md`
- Modify: `docs/BUILD_PLAN.md`
- Modify: `docs/TEAM_OWNERSHIP.md`
- Modify: `docs/CURRENT_STAGE.md`
- Modify: `docs/MONITORING_INTELLIGENCE_LAB.md`
- Modify: `docs/PHASE_5_BACKEND_REVIEW.md`
- Modify: `docs/superpowers/specs/2026-09-01-monitoring-intelligence-lab-design.md`

**Interfaces:**
- Consumes: founder-approved design in the linked spec.
- Produces: source-of-truth V1.9 semantics used by every later task.

- [x] **Step 1: Update product ownership language**

Replace statements saying deterministic policy owns urgent/final disposition with this exact semantic split: deterministic code detects and measures anomaly episodes; AI owns explanations, operational severity, and recommended action; deterministic code owns validation and lifecycle mechanics; caregivers own real-world action.

- [x] **Step 2: Publish the three-stage data flow and failure behavior**

Document `recall_router → parallel_precision_specialists → final_integrator_reviewer`, one optional targeted repair, and visible `analysis_pending` / `needs_staff_review` behavior.

- [x] **Step 3: Version the shared contract**

Add a V1.9 contract note and exact stage/final-analysis shapes matching Task 2. Make clear that this is a breaking intelligence-ownership change but not a frontend route removal.

- [x] **Step 4: Check documentation consistency**

Run:

```bash
rg -n "urgent deterministic|LLM-independent|deterministic policy.*disposition|cannot suppress" AGENTS.md docs
```

Expected: historical research may retain old wording; active source-of-truth docs do not contradict V1.9.

- [x] **Step 5: Commit**

```bash
git add AGENTS.md docs/PRD.md docs/ARCHITECTURE.md docs/DATA_CONTRACT.md docs/BUILD_PLAN.md docs/TEAM_OWNERSHIP.md docs/CURRENT_STAGE.md docs/MONITORING_INTELLIGENCE_LAB.md docs/PHASE_5_BACKEND_REVIEW.md docs/superpowers/specs/2026-09-01-monitoring-intelligence-lab-design.md
git commit -m "docs: align product around multi-agent interpretation"
```

### Task 2: Add strict multi-agent analysis contracts

**Files:**
- Create: `backend/app/ai/analysis_contracts.py`
- Modify: `backend/app/ai/__init__.py`
- Create: `tests/ai/test_analysis_contracts.py`

**Interfaces:**
- Consumes: existing `EvidencePacket`, controlled category/disposition enums, and exact evidence identifiers.
- Produces: `AnalysisStage`, `AnalysisState`, `ConfidenceBand`, `Severity`, `Possibility`, `RoutingPlan`, `SpecialistAssessment`, `FinalAnalysis`, `AnalysisRun`, `StageRequest`, `StageResponse`, and `StructuredAnalysisClient`.

- [x] **Step 1: Write failing contract tests**

Cover normalization and rejection of blank IDs, duplicate specialists, duplicate possibility IDs, confidence outside the controlled bands, final claims with nonexistent evidence references, and inconsistent action/severity combinations. Use literal fixtures; do not compute expected values with production helpers.

- [x] **Step 2: Verify the tests fail for missing contracts**

Run:

```bash
pytest tests/ai/test_analysis_contracts.py -q
```

Expected: import failure because `analysis_contracts.py` does not exist.

- [x] **Step 3: Implement immutable typed contracts**

The public protocol is:

```python
class StructuredAnalysisClient(Protocol):
    def analyze(self, request: StageRequest) -> StageResponse: ...

@dataclass(frozen=True)
class StageRequest:
    stage: AnalysisStage
    anomaly_id: str
    packet_revision: int
    skill_names: tuple[str, ...]
    prompt: str
    payload_json: str
    response_schema: dict[str, object]
    request_fingerprint: str
    model_tier: str

@dataclass(frozen=True)
class FinalAnalysis:
    analysis_id: str
    anomaly_id: str
    packet_revision: int
    possibilities: tuple[Possibility, ...]
    severity: Severity
    recommended_disposition: RecommendedDisposition
    caregiver_summary: str
    next_step: str
    missing_information: tuple[str, ...]
    specialist_disagreements: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    coverage_complete: bool
```

Do not add free-form medical diagnosis fields or chain-of-thought fields.

- [x] **Step 4: Run focused tests**

```bash
pytest tests/ai/test_analysis_contracts.py -q
```

Expected: all pass.

- [x] **Step 5: Commit**

```bash
git add backend/app/ai/analysis_contracts.py backend/app/ai/__init__.py tests/ai/test_analysis_contracts.py
git commit -m "feat: define multi-agent analysis contracts"
```

### Task 3: Add versioned recall, specialist, and final-review skills

**Files:**
- Create: `prompts/monitoring/recall_router.md`
- Create: `prompts/monitoring/specialists/signal_integrity.md`
- Create: `prompts/monitoring/specialists/movement_fall.md`
- Create: `prompts/monitoring/specialists/physiology.md`
- Create: `prompts/monitoring/specialists/inactivity_sleep.md`
- Create: `prompts/monitoring/specialists/presence_room.md`
- Create: `prompts/monitoring/specialists/routine_context.md`
- Create: `prompts/monitoring/specialists/repetition_escalation.md`
- Create: `prompts/monitoring/specialists/unknown_cross_domain.md`
- Create: `prompts/monitoring/final_integrator_reviewer.md`
- Create: `backend/app/ai/analysis_skills.py`
- Create: `tests/ai/test_analysis_skills.py`

**Interfaces:**
- Consumes: `AnalysisStage` and stable specialist names from Task 2.
- Produces: `AnalysisSkill`, `load_analysis_skill(name)`, `analysis_skill_registry()`, and deterministic fallback routing by measured anomaly family.

- [x] **Step 1: Write failing registry and behavior tests**

Assert that every declared specialist resolves to one versioned file, recall instructions require broad plausible coverage, specialist instructions require evidence for/against, and final instructions require combination, multiple retained possibilities, completeness review, and no hallucinated facts.

- [x] **Step 2: Verify failure**

```bash
pytest tests/ai/test_analysis_skills.py -q
```

- [x] **Step 3: Implement the focused skill registry and files**

Each skill must declare purpose, bounded inputs, structured outputs, forbidden behavior, uncertainty rules, evidence-reference rules, and concise non-diagnostic language. The final skill performs synthesis and neutral review in one call.

- [x] **Step 4: Run focused tests**

```bash
pytest tests/ai/test_analysis_skills.py -q
```

- [x] **Step 5: Commit**

```bash
git add prompts/monitoring backend/app/ai/analysis_skills.py tests/ai/test_analysis_skills.py
git commit -m "feat: add recall specialist and final analysis skills"
```

### Task 4: Build bounded stage context and deterministic grounding validation

**Files:**
- Create: `backend/app/ai/analysis_context.py`
- Create: `backend/app/ai/analysis_validation.py`
- Create: `tests/ai/test_analysis_context.py`
- Create: `tests/ai/test_analysis_validation.py`

**Interfaces:**
- Consumes: `EvidencePacket`, `ResidentMemory`, stage contracts, and skill registry.
- Produces: `build_recall_request`, `build_specialist_request`, `build_final_request`, `validate_routing_plan`, `validate_specialist_assessment`, and `validate_final_analysis`.

- [x] **Step 1: Write failing bounded-context tests**

Prove that requests contain exact evidence facts and relevant context, exclude unrelated resident entries, never include hidden expected labels, and give each stage only the previous structured results it needs.

- [x] **Step 2: Write failing grounding tests**

Prove that nonexistent evidence references, skipped routed possibilities, unknown specialist names, invented measurements, unsupported resident attribution, and missing coverage declarations are rejected. Prove that `observe` remains valid for a strong anomaly.

- [x] **Step 3: Verify both files fail for missing behavior**

```bash
pytest tests/ai/test_analysis_context.py tests/ai/test_analysis_validation.py -q
```

- [x] **Step 4: Implement canonical JSON builders and validators**

Fingerprint each request from canonical stage, packet revision, versions, skills, and payload. Validation may reject or request repair but must not alter severity or action.

- [x] **Step 5: Run focused tests**

```bash
pytest tests/ai/test_analysis_context.py tests/ai/test_analysis_validation.py -q
```

- [x] **Step 6: Commit**

```bash
git add backend/app/ai/analysis_context.py backend/app/ai/analysis_validation.py tests/ai/test_analysis_context.py tests/ai/test_analysis_validation.py
git commit -m "feat: build grounded multi-agent analysis requests"
```

### Task 5: Implement checkpointed three-stage orchestration

**Files:**
- Create: `backend/app/ai/analysis_orchestration.py`
- Create: `tests/ai/test_analysis_orchestration.py`

**Interfaces:**
- Consumes: one client per capability tier, context builders, validators, and stage contracts.
- Produces: `MultiAgentAnalysisOrchestrator.analyze(packet, resident_memory, relevant_context_entry_ids) -> AnalysisRun`.

- [ ] **Step 1: Write failing happy-path test**

Use a deterministic scripted client and assert exact call order: one recall call, selected specialist calls in one parallel wave, then one final call. Assert the final result retains two credible possibilities and the specialists do not receive one another's output.

- [ ] **Step 2: Write failing resilience tests**

Cover recall failure with deterministic routing-only fallback, one missing specialist, invalid final output followed by exactly one targeted repair, second invalid output becoming `needs_staff_review`, stage checkpoint reuse, and exact replay idempotency.

- [ ] **Step 3: Verify failure**

```bash
pytest tests/ai/test_analysis_orchestration.py -q
```

- [ ] **Step 4: Implement the orchestrator**

Use `ThreadPoolExecutor` with a configured maximum of four specialist workers. Preserve input order in saved results, record failed specialists explicitly, and never loop repairs beyond one attempt.

- [ ] **Step 5: Run focused tests repeatedly**

```bash
pytest tests/ai/test_analysis_orchestration.py -q
pytest tests/ai/test_analysis_orchestration.py -q
```

Expected: deterministic identical outcomes across both runs.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ai/analysis_orchestration.py tests/ai/test_analysis_orchestration.py
git commit -m "feat: orchestrate recall specialists and final review"
```

### Task 6: Add a generic Gemini structured-stage adapter

**Files:**
- Modify: `backend/app/ai/gemini.py`
- Create: `tests/ai/test_gemini_analysis_client.py`
- Modify: `tests/ai/test_gemini_client.py`

**Interfaces:**
- Consumes: `StageRequest` and existing `GeminiTransport` retry/rate-limit boundary.
- Produces: `GeminiStructuredAnalysisClient.analyze(request) -> StageResponse` while preserving `GeminiLLMClient` as a temporary legacy compatibility adapter.

- [ ] **Step 1: Write failing provider tests**

Assert provider model pinning, per-stage JSON schema use, low thinking for recall, stronger thinking configuration for precision/final tiers, 180-second maximum timeout, sanitized errors, rate-limit pacing, and exact raw structured payload return.

- [ ] **Step 2: Verify failure**

```bash
pytest tests/ai/test_gemini_analysis_client.py -q
```

- [ ] **Step 3: Implement the shared transport executor and stage client**

Refactor retry/pacing into one internal executor used by both legacy and staged clients. Do not log or persist API keys.

- [ ] **Step 4: Run all Gemini tests and a secret scan**

```bash
pytest tests/ai/test_gemini_client.py tests/ai/test_gemini_analysis_client.py -q
git grep -nE 'AIza|AQ\.[A-Za-z0-9_-]{20,}' -- ':!*.md' || true
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai/gemini.py tests/ai/test_gemini_client.py tests/ai/test_gemini_analysis_client.py
git commit -m "feat: add Gemini multi-stage analysis provider"
```

### Task 7: Integrate AI-owned disposition with monitoring and event lifecycle

**Files:**
- Modify: `backend/app/intelligence/policy.py`
- Modify: `backend/app/intelligence/orchestration.py`
- Modify: `backend/app/intelligence/__init__.py`
- Modify: `tests/intelligence/test_policy_orchestration.py`
- Create: `tests/intelligence/test_multi_agent_monitoring_flow.py`

**Interfaces:**
- Consumes: trusted `AnalysisRun.final_analysis` from Task 5.
- Produces: anomaly-first processing, pending analysis states, AI-owned severity/action, and existing idempotent event mechanics.

- [ ] **Step 1: Replace the obsolete regression expectation**

Write failing tests proving a strong anomaly plus trusted `observe` remains observation/history without creating caregiver work, and proving AI unavailability yields visible pending/staff-review state rather than an objective severity guess.

- [ ] **Step 2: Write failing end-to-end monitoring tests**

Cover a routine bathroom explanation, ambiguous movement retaining two possibilities, high action creating one event, urgent action setting critical priority, duplicate frame replay, provider recovery, acknowledgment/cooldown, recurrence, and multi-person room-level uncertainty.

- [ ] **Step 3: Verify the new tests fail against the old policy**

```bash
pytest tests/intelligence/test_policy_orchestration.py tests/intelligence/test_multi_agent_monitoring_flow.py -q
```

- [ ] **Step 4: Implement AI-owned disposition**

Add a final-analysis policy path that maps the AI's trusted action and severity into existing event mechanics without comparing anomaly strength. Keep operational device-health warnings separate from resident interpretation. Retain legacy one-shot mode only for migration/evaluation compatibility and mark it as legacy.

- [ ] **Step 5: Run intelligence regression tests**

```bash
pytest tests/intelligence tests/event_domain -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/intelligence backend/app/ai tests/intelligence
git commit -m "feat: let trusted AI analysis own event disposition"
```

### Task 8: Persist analysis runs and publish the backend/frontend handoff contract

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/db/migrations/versions/0007_multi_agent_analysis.py`
- Modify: `backend/app/db/intelligence_mappers.py`
- Modify: `backend/app/db/intelligence_repositories.py`
- Modify: `backend/app/contracts/events.py`
- Modify: `backend/app/api/v1/events.py`
- Modify: `backend/app/services/queries.py`
- Modify: `tests/persistence/test_intelligence_repositories.py`
- Modify: `tests/api/test_read_api.py`
- Modify: `tests/api/test_openapi_contract.py`

**Interfaces:**
- Consumes: canonical `AnalysisRun` and final analysis.
- Produces: tenant-scoped, versioned persistence and a consolidated event-analysis read contract without exposing raw agent transcripts or chain-of-thought.

- [ ] **Step 1: Write failing mapper/repository tests**

Prove tenant isolation, anomaly-revision binding, canonical round trip, idempotent save, exact stage provenance, rejected fabricated evidence, and resume from partial stage checkpoints.

- [ ] **Step 2: Write failing API contract tests**

Add response models for pending/final analysis, retained possibilities, confidence bands, uncertainty, next step, evidence references, and model/skill version metadata. Assert the existing event endpoint remains backward compatible while an analysis field is additive.

- [ ] **Step 3: Verify failure**

```bash
pytest tests/persistence/test_intelligence_repositories.py tests/api/test_read_api.py tests/api/test_openapi_contract.py -q
```

- [ ] **Step 4: Implement migration, canonical persistence, and query mapping**

Use one tenant-scoped analysis-run row per anomaly revision with canonical JSON envelopes and shadow columns for IDs/state/version. Do not persist prompts containing unnecessary resident history or any credential.

- [ ] **Step 5: Run persistence and API tests**

```bash
pytest tests/persistence tests/api -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/db backend/app/contracts/events.py backend/app/api/v1/events.py backend/app/services/queries.py tests/persistence tests/api
git commit -m "feat: persist and expose multi-agent analysis"
```

### Task 9: Extend evaluation campaigns for routing, precision, synthesis, and latency

**Files:**
- Modify: `evals/monitoring/scenarios.py`
- Modify: `evals/monitoring/grading.py`
- Modify: `evals/monitoring/metrics.py`
- Modify: `evals/monitoring/artifacts.py`
- Modify: `evals/monitoring/campaign.py`
- Modify: `evals/monitoring/cli.py`
- Create: `tests/evals/test_multi_agent_evaluation.py`
- Modify: `tests/evals/test_monitoring_execution_capture.py`

**Interfaces:**
- Consumes: `AnalysisRun` stage records and existing 12-cluster scenario truth.
- Produces: stage-specific and end-to-end metrics, resumable artifacts, and provider/model/skill comparisons.

- [ ] **Step 1: Write failing evaluation tests**

Use literal scenario expectations to measure possibility recall, routing accuracy, specialist precision, hallucinations, alternative preservation, final action/severity agreement, repair rate, stage latency, total latency, calls, and unavailable-stage behavior.

- [ ] **Step 2: Verify failure**

```bash
pytest tests/evals/test_multi_agent_evaluation.py tests/evals/test_monitoring_execution_capture.py -q
```

- [ ] **Step 3: Implement metrics and artifact capture**

Preserve real attempted/completed counts. Save stage outputs and errors with credential redaction and checksums. Keep deterministic million-case evidence separate from live multi-agent AI evidence.

- [ ] **Step 4: Run smoke and canonical campaigns**

```bash
python3 -m evals.monitoring.cli smoke --output-dir eval-results/monitoring/multi_agent_smoke
python3 -m evals.monitoring.cli pr --output-dir eval-results/monitoring/multi_agent_pr
```

- [ ] **Step 5: Commit**

```bash
git add evals/monitoring tests/evals
git commit -m "feat: evaluate multi-agent monitoring intelligence"
```

### Task 10: Complete regression, live Gemini proof, review, and handoff documentation

**Files:**
- Modify: `docs/MONITORING_INTELLIGENCE_LAB.md`
- Modify: `docs/CURRENT_STAGE.md`
- Create: `docs/MULTI_AGENT_BACKEND_REVIEW.md`
- Modify: `graphify-out/*` through `graphify update .`

**Interfaces:**
- Consumes: all completed tasks.
- Produces: reproducible verification evidence and a plain-language cofounder handoff.

- [ ] **Step 1: Run focused and complete automated verification**

```bash
pytest tests/ai tests/intelligence tests/evals tests/persistence tests/api tests/event_domain -q
pytest -q
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

- [ ] **Step 2: Run deterministic evaluation checkpoints**

```bash
python3 -m evals.monitoring.cli smoke --output-dir eval-results/monitoring/multi_agent_final_smoke
python3 -m evals.monitoring.cli pr --output-dir eval-results/monitoring/multi_agent_final_pr
```

- [ ] **Step 3: Run a bounded live Gemini end-to-end proof**

Load the ignored local key without printing it, run the smallest complete recall → specialists → final pipeline case permitted by the current free quota, and save the exact attempted/completed/failure counts. If quota prevents completion, report the quota result without claiming a pass.

- [ ] **Step 4: Review implementation against every completion criterion**

Inspect the full diff from `f4020b5`, run a dedicated code-review pass, correct all critical/important findings, and rerun affected tests.

- [ ] **Step 5: Refresh the code graph and documentation**

```bash
graphify update .
```

Document what is implemented, what the tests prove, live-model evidence, frontend contract changes, and what still requires real sensors, representative environments, caregiver review, privacy/security review, and later clinical validation.

- [ ] **Step 6: Final secret and diff checks**

```bash
git diff --check
git grep -nE 'AIza|AQ\.[A-Za-z0-9_-]{20,}' -- ':!*.md' || true
git status --short
```

- [ ] **Step 7: Commit**

```bash
git add docs graphify-out
git commit -m "docs: record multi-agent backend verification"
```
