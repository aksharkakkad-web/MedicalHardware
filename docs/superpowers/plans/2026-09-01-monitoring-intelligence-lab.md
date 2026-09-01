# Monitoring Intelligence Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task by task.

**Goal:** Build a reproducible evaluation lab that proves the existing monitoring pipeline behaves safely across normal human variation, anomalies, feedback, learning, provider failures, and a controlled live Gemini campaign.

**Architecture:** Extend the existing Phase 5 engine and scenario replay instead of creating a second monitoring system. Every generated case travels through the same alignment, filtering, anomaly, event, interpretation, feedback, and memory contracts used by the product. Deterministic offline runs establish software correctness at scale; strict live-provider runs evaluate model quality without allowing the model to control urgent safety decisions.

**Tech Stack:** Python 3.12, pytest, standard-library HTTP/JSON/gzip/hashlib/concurrency, existing FastAPI/SQLAlchemy/Pydantic application contracts, Gemini REST API for the development-model campaign.

**Spec:** `docs/superpowers/specs/2026-09-01-monitoring-intelligence-lab-design.md`

## Global Constraints

- Preserve the existing Phase 5 engine, event lifecycle, safety path, and 24-case replay as the system of record.
- Use test-driven development: add a failing test, observe the failure, make the smallest implementation, then rerun the focused and broader suites.
- Never commit, print, copy into artifacts, or include in command output any provider key.
- Treat AI interpretation as bounded advice. Deterministic urgent events must remain available even if AI fails, times out, or returns invalid content.
- Acknowledgment silences repeated notification behavior but does not erase the anomaly, close the clinical story, or train memory by itself.
- Only explicit feedback may change resident memory, and all proposed changes remain attributable and reversible.
- Artifacts are append-only, resumable, checksummed, redacted, and written beneath ignored `eval-results/monitoring/<run-id>/` directories.
- Large numeric targets are campaign targets, not permission to fabricate results. Reports must distinguish attempted, completed, valid, failed, skipped, quota-limited, and resumed work.
- No result from toy or synthetic data may be described as clinical validation or hardware validation.

---

## Task 1: Lock the taxonomy and case contracts

**Files:**

- Create: `evals/monitoring/taxonomy.py`
- Modify: `evals/monitoring/scenarios.py`
- Test: `tests/evals/test_monitoring_taxonomy.py`

### Steps

- [ ] Add a failing test asserting exactly 12 documented scenario clusters, stable identifiers, safety criticality, expected event behavior, expected interpretation behavior, and allowed feedback effects.
- [ ] Run `pytest -q tests/evals/test_monitoring_taxonomy.py` and confirm the missing-module failure.
- [ ] Define immutable contracts such as:

```python
@dataclass(frozen=True)
class ScenarioCluster:
    cluster_id: str
    title: str
    safety_critical: bool
    description: str

@dataclass(frozen=True)
class ScenarioExpectation:
    event_outcome: str
    interpretation_outcome: str
    feedback_outcome: str
    forbidden_outcomes: tuple[str, ...]
```

- [ ] Cover normal routine, random timing variation, bathroom/temporary absence, guests/multiple people, sleep/inactivity, falls, respiration/vital concern, degraded sensing, new-but-benign behavior, repeated behavior, contradictory evidence, and provider/system failure.
- [ ] Map every existing 24-case scenario to one cluster without changing its expected replay behavior.
- [ ] Run the focused test and `pytest -q tests/evals/test_monitoring_replay.py`.
- [ ] Commit: `test: lock monitoring evaluation taxonomy`

## Task 2: Make existing scenarios safely transformable and observable

**Files:**

- Modify: `evals/monitoring/scenarios.py`
- Create: `evals/monitoring/transforms.py`
- Test: `tests/evals/test_monitoring_transforms.py`
- Test: `tests/evals/test_monitoring_execution_capture.py`

### Steps

- [ ] Add failing tests proving a caller can run one named scenario, inject an optional frame-sequence transform, choose an `LLMClient`, and capture the exact interpretation requests/results without changing default replay bytes.
- [ ] Run the tests and observe the absent interfaces.
- [ ] Add a narrow execution result:

```python
@dataclass(frozen=True)
class ScenarioExecution:
    scenario_id: str
    record: Mapping[str, object]
    interpretation_requests: tuple[InterpretationRequest, ...]
    interpretation_results: tuple[InterpretationResult, ...]
```

- [ ] Add `run_scenario(...)` while preserving `run_scenarios()` as a compatibility wrapper.
- [ ] Implement deterministic transforms by reconstructing normalized observations and calling the real aligner: safe time shift, bounded numeric jitter, source dropout, quality downgrade, duplicated input, and bounded reordering.
- [ ] Reject transforms that remove every source, create non-finite values, violate time ordering after normalization, or alter immutable identity fields.
- [ ] Prove identical seed + case produces byte-identical records, while different seeds create distinct but contract-valid inputs.
- [ ] Run focused tests, replay tests, and `pytest -q tests/ai tests/intelligence`.
- [ ] Commit: `refactor: expose transformable monitoring scenario executions`

## Task 3: Complete feedback and resident-memory skill contracts

**Files:**

- Create: `backend/app/ai/prompts/monitoring/feedback_agent.md`
- Create: `backend/app/ai/prompts/monitoring/resident_memory_updater.md`
- Modify: `backend/app/ai/skills.py`
- Test: `tests/ai/test_monitoring_skills.py`
- Test: `tests/ai/test_feedback_memory_boundaries.py`

### Steps

- [ ] Add failing tests for registry discovery, versioning, required safety language, bounded inputs, structured outputs, and separation between feedback interpretation and memory mutation.
- [ ] Run the focused tests and confirm the new skills are absent.
- [ ] Write the feedback skill to classify explicit operator input without inventing measurements or treating acknowledgment as feedback.
- [ ] Write the resident-memory updater skill to propose one of `no_change`, `add_candidate`, `reinforce`, `revise`, or `retire`, with evidence references, confidence, scope, effective time, expiry/review time, and a human-readable reason.
- [ ] Register both skills with stable bundle versions and compatible schema versions.
- [ ] Add adversarial tests proving malicious/free-text feedback cannot alter protected identity, tenant, urgent-safety, or raw-measurement fields.
- [ ] Run focused tests and all AI tests.
- [ ] Commit: `feat: add bounded feedback and resident memory skills`

## Task 4: Add a strict Gemini 3.7 Flash provider

**Files:**

- Create: `backend/app/ai/gemini.py`
- Modify: `backend/app/ai/__init__.py`
- Test: `tests/ai/test_gemini_client.py`
- Test: `tests/ai/test_gemini_contract_fixtures.py`

### Steps

- [ ] Add failing transport-level tests for request construction, `thinkingLevel: low`, JSON response schema, pinned model identifier, retry classification, timeout behavior, refusal/empty response, malformed JSON, and redacted errors.
- [ ] Run focused tests and confirm failure.
- [ ] Define an injectable transport so tests never need network access:

```python
class GeminiTransport(Protocol):
    def generate(self, *, model: str, api_key: str, body: bytes, timeout: float) -> bytes: ...

class GeminiLLMClient:
    def interpret(self, request: InterpretationRequest) -> InterpretationResult: ...
```

- [ ] Read `GEMINI_API_KEY` only at construction/runtime, never at import, and never include it in representations or exceptions.
- [ ] Use REST `generateContent`, `responseMimeType: application/json`, a strict response schema, low thinking, conservative temperature, and sufficient output tokens.
- [ ] Convert all provider output into the existing `InterpretationResult`, then pass it through existing provenance/factual validation before it can affect product state.
- [ ] Retry only transient statuses with bounded exponential backoff and jitter; do not retry schema/safety failures.
- [ ] Add recorded key-free fixtures for valid, invalid, blocked, empty, rate-limited, server-error, and truncated responses.
- [ ] Run focused tests, AI tests, and a secret-pattern scan over tracked files.
- [ ] Commit: `feat: add strict Gemini interpretation provider`

## Task 5: Generate reviewable canonical timelines and deterministic mass cases

**Files:**

- Create: `evals/monitoring/generation.py`
- Modify: `evals/monitoring/taxonomy.py`
- Test: `tests/evals/test_monitoring_generation.py`

### Steps

- [ ] Add failing tests requiring at least 120 stable founder-reviewable cases, all 12 clusters, both normal and anomalous outcomes, boundary cases, explicit expectations, and deterministic generation.
- [ ] Run the focused test and confirm failure.
- [ ] Define serializable descriptors rather than storing a million inputs in memory:

```python
@dataclass(frozen=True)
class GeneratedCase:
    case_id: str
    canonical_id: str
    cluster_id: str
    seed: int
    transform_spec: Mapping[str, object]
    expectation: ScenarioExpectation
```

- [ ] Derive five carefully bounded variants from each existing scenario for a minimum 120-case canonical set, with human-readable names and rationales.
- [ ] Generate larger cases lazily from `(canonical_id, seed, perturbation_pass)` and guarantee stable IDs/hashes.
- [ ] Balance cluster, severity, normal variation, ambiguity, evidence quality, multi-person, learning state, and provider-failure dimensions.
- [ ] Ensure common normal behavior such as bathroom trips, visitors, variable routine timing, and temporary room absence is represented without hard-coded exact schedules.
- [ ] Run focused tests and existing replay tests.
- [ ] Commit: `feat: generate balanced monitoring timelines`

## Task 6: Build grading, metrics, and hard safety gates

**Files:**

- Create: `evals/monitoring/grading.py`
- Modify: `evals/monitoring/metrics.py`
- Test: `tests/evals/test_monitoring_grading.py`
- Test: `tests/evals/test_monitoring_hard_gates.py`

### Steps

- [ ] Add failing tests for deterministic grading, abstention quality, unsupported claims, provenance, urgency preservation, event lifecycle, duplicate prevention, learning safety, repeatability, and cluster-level confusion accounting.
- [ ] Run the tests and confirm missing behavior.
- [ ] Separate hard failures from score-based metrics:

```python
@dataclass(frozen=True)
class CaseGrade:
    passed: bool
    hard_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    scores: Mapping[str, float]
    evidence: Mapping[str, object]
```

- [ ] Implement zero-tolerance gates for urgent-event suppression, invented measurements reaching product state, unsupported attribution, baseline contamination, duplicate open events, replay mismatch, cross-tenant leakage, invalid output acceptance, AI blocking the deterministic path, unsafe memory mutation, and acknowledgment closing an unresolved anomaly.
- [ ] Calculate per-cluster precision/recall proxies, false-notification burden, abstention appropriateness, schema validity, provenance validity, latency, repetition stability, and learning-loop correctness.
- [ ] Grade deterministic system behavior from exact expectations; grade model language only from structured fields and evidence links, not stylistic preference.
- [ ] Run focused tests, monitoring eval tests, AI tests, and intelligence tests.
- [ ] Commit: `feat: grade monitoring intelligence safety and quality`

## Task 7: Add durable, redacted, resumable artifacts

**Files:**

- Create: `evals/monitoring/artifacts.py`
- Modify: `.gitignore`
- Test: `tests/evals/test_monitoring_artifacts.py`

### Steps

- [ ] Add failing tests for run creation, gzip JSONL chunks, atomic writes, checkpoints, resume, checksums, manifest consistency, redaction, crash recovery, and no duplicate completion records.
- [ ] Run the focused tests and confirm failure.
- [ ] Ignore `eval-results/` while keeping schemas and code tracked.
- [ ] Write a run directory containing `manifest.json`, `cases/*.jsonl.gz`, `responses/*.jsonl.gz`, `failures.jsonl.gz`, `metrics.json`, `hard-gates.json`, `comparison.json`, `report.md`, `checkpoint.json`, and `checksums.sha256` as applicable.
- [ ] Store a one-way key fingerprint only if needed to identify a credential change; never store the key, authorization headers, or raw environment.
- [ ] Redact field names and string patterns associated with credentials before serialization and again before final checksumming.
- [ ] Resume from the last fully checksummed chunk and make rerunning an already-complete case idempotent.
- [ ] Run focused tests and a repository secret scan.
- [ ] Commit: `feat: persist resumable monitoring evaluation evidence`

## Task 8: Build the campaign engine and operator CLI

**Files:**

- Create: `evals/monitoring/campaign.py`
- Create: `evals/monitoring/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/evals/test_monitoring_campaign.py`
- Test: `tests/evals/test_monitoring_cli.py`

### Steps

- [ ] Add failing tests for `smoke`, `pr`, `mass`, `gemini`, `compare`, and `release` modes; bounded case counts; seed selection; worker count; rate limits; retries; stop-on-hard-gate; checkpointing; resume; and exit codes.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement a chunked campaign runner that lazily creates cases, executes the real scenario pipeline, grades results, and writes artifacts.
- [ ] Use parallel workers only for deterministic offline cases. Keep live-provider concurrency/rate limits explicit and conservative.
- [ ] Support commands shaped like:

```bash
python -m evals.monitoring.cli mass --cases 100000 --passes 10 --workers auto
python -m evals.monitoring.cli gemini --cases 25000 --resume <run-id>
python -m evals.monitoring.cli compare --run-a <id> --run-b <id>
```

- [ ] Make `smoke` run a small cross-cluster set, `pr` run all canonical timelines, `mass` target 100,000 timelines × 10 passes, and `gemini` operate only on AI-eligible cases.
- [ ] Stop dispatching new work on a hard safety failure while preserving completed evidence and a resumable checkpoint.
- [ ] Report quota/rate limits honestly rather than marking unattempted calls as passes.
- [ ] Add a console entry point only if it improves current project conventions; otherwise keep `python -m` as the stable interface.
- [ ] Run focused tests and `pytest -q tests/evals`.
- [ ] Commit: `feat: orchestrate monitoring evaluation campaigns`

## Task 9: Add model comparison and final release-gate logic

**Files:**

- Create: `evals/monitoring/comparison.py`
- Modify: `evals/monitoring/campaign.py`
- Test: `tests/evals/test_monitoring_comparison.py`
- Test: `tests/evals/test_monitoring_release_gate.py`

### Steps

- [ ] Add failing tests for paired case comparison, provider/version fingerprints, non-comparable run rejection, regression thresholds, hard-gate precedence, and incomplete-run labeling.
- [ ] Run the focused tests and confirm failure.
- [ ] Compare identical saved case IDs and inputs across providers, prompts, skill bundles, or versions.
- [ ] Produce per-cluster deltas for validity, supported conclusions, appropriate abstention, disposition agreement, latency, stability, and false-notification burden.
- [ ] Define the later production gate as 5,000 Terra cases plus 1,000 Sol fallback/critical cases, but require explicit cost approval and credentials before dispatching paid calls.
- [ ] Never let a stronger average score override any hard safety failure.
- [ ] Run focused tests and all eval tests.
- [ ] Commit: `feat: compare models and enforce release gates`

## Task 10: Document the workflow and prove the small-to-large ladder

**Files:**

- Create: `docs/MONITORING_INTELLIGENCE_LAB.md`
- Modify: `docs/BACKEND_IMPLEMENTATION_STATUS.md`
- Modify: `docs/PHASED_EXECUTION_ROADMAP.md`
- Test: `tests/evals/test_monitoring_docs_commands.py`

### Steps

- [ ] Add a failing documentation-contract test that parses every documented command and verifies the referenced module, mode, and required files exist.
- [ ] Run the focused test and confirm failure.
- [ ] Explain the product flow in plain language: signals → aligned evidence → anomaly filter → deterministic event → AI explanation → dashboard action → feedback → guarded resident memory.
- [ ] Document exact commands for unit tests, smoke, canonical PR set, offline mass run, live Gemini checkpoint, resume, comparison, and report inspection.
- [ ] State clearly what synthetic evidence proves and what still requires hardware, real resident data, clinical review, and frontend integration.
- [ ] Run the focused documentation test.
- [ ] Commit: `docs: explain monitoring intelligence validation workflow`

## Task 11: Run reviews and complete the offline evidence campaign

**Files:**

- Generated, ignored: `eval-results/monitoring/<run-id>/...`
- Modify only if defects are found: implementation and tests above

### Steps

- [ ] Run formatter/linter commands configured by the repository, `git diff --check`, and the full backend test suite.
- [ ] Run the existing 24-case replay and confirm its canonical bytes remain deterministic.
- [ ] Run `smoke`, inspect every failure/warning, fix defects with a new failing regression test, and rerun.
- [ ] Run all 120+ canonical timelines and review cluster coverage plus hard gates.
- [ ] Run a medium offline campaign first (for example 10,000 executions) to measure throughput and artifact growth.
- [ ] Estimate the full 1,000,000-execution runtime from measured throughput, then execute in resumable chunks while checking hard gates and checksums after each checkpoint.
- [ ] If a safety failure appears, stop new dispatch, preserve evidence, reproduce it as a focused test, fix, rerun the affected cluster, then restart/resume the campaign.
- [ ] Complete a final clean offline run and save attempted/completed counts, duration, failures, metrics, seeds, versions, and checksums.
- [ ] Commit any regression fixes with focused messages; do not commit generated campaign artifacts or credentials.

## Task 12: Run the controlled Gemini development campaign

**Files:**

- Generated, ignored: `eval-results/monitoring/<run-id>/...`
- Modify only if defects are found: provider, prompts, skills, grader, and tests above

### Steps

- [ ] Verify the credential exists without displaying it and make one schema-valid live smoke call.
- [ ] Run a 12-cluster live smoke set and inspect provider validity, factual support, disposition, uncertainty, latency, token use, and redaction.
- [ ] Run a 100-case pilot; add regression tests for any discovered contract failure before changing prompts or provider logic.
- [ ] Run a 1,000-case checkpoint and review per-cluster behavior, rate limits, retries, and costs reported by the free tier.
- [ ] Continue toward the first 25,000 saved live interpretations, resumably and within the account's free quota. If quota prevents completion, save the exact completed count and quota response, and leave the campaign ready to resume; never claim 25,000 were completed unless the artifacts prove it.
- [ ] Build the fixed 10,000-case comparison set and the 2,000 critical cases intended for five-run stability testing, even if provider quota postpones some calls.
- [ ] Confirm zero hard-gate failures. Any hard failure stops the campaign and enters the regression-fix loop.
- [ ] Produce `report.md` with plain-English findings, known limits, failed or deferred calls, and the exact next paid Terra/Sol gate. Do not call Terra/Sol without separate cost approval.

## Final Verification Checklist

- [ ] `git status --short` contains only intended tracked changes and ignored local artifacts.
- [ ] `git diff --check` passes.
- [ ] Placeholder scan (`rg -n "TODO|TBD|FIXME|placeholder|not implemented"`) finds no unfinished production or test contract introduced by this work.
- [ ] Full backend tests pass from a clean process.
- [ ] Existing replay is byte-deterministic.
- [ ] At least 120 canonical timelines cover all 12 clusters.
- [ ] Offline campaign evidence reports real attempted/completed counts up to the 1,000,000 target.
- [ ] Gemini evidence reports real attempted/completed counts and any quota limit without exaggeration.
- [ ] All artifacts validate against their checksums and contain no credentials.
- [ ] Every spec requirement is mapped to code, test, artifact, or an explicitly documented external-validation limitation.
- [ ] Final report separates: implemented, unit-tested, synthetic-tested, live-model-tested, frontend-integration pending, hardware-data pending, and clinical-validation pending.
