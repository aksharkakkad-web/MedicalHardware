# Phase 5 Monitoring Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete independent backend intelligence path from normalized simulated observations through personal baselines, anomaly evidence, situation-specific AI interpretation, deterministic disposition, durable caregiver events, and reproducible evaluation.

**Architecture:** Extend the existing monitoring, calibration, resident-memory, and event foundations. New focused intelligence modules use immutable dataclasses and pure deterministic functions; database repositories persist the state that must survive restart. Non-urgent anomaly evidence is interpreted before deterministic disposition, while urgent synthetic safety evidence creates a provisional event without waiting for AI.

**Tech Stack:** Python 3.12+, standard library statistics, Pydantic v2, SQLAlchemy 2, Alembic, pytest, Markdown skill files; no numerical or live-LLM SDK dependency.

**Spec:** `docs/superpowers/specs/2026-08-28-phase5-monitoring-intelligence-design.md`

## Global Constraints

- Phase 5 consumes normalized simulated observations; raw sensor parsing and edge transport remain Phase 6.
- V1 supports one assigned resident per room and never guesses identity during possible-multiple-person periods.
- Missing or unusable values are never zero-filled, forward-filled, or imputed.
- Only `GOOD` feature windows with valid attribution and no anomaly/freeze guard may update numerical normality.
- All thresholds and durations are versioned, synthetic, test-only policy values; no medical threshold or clinical claim may be introduced.
- Numerical anomaly lifecycle is separate from caregiver event lifecycle and caregiver acknowledgment never closes an anomaly.
- Non-urgent flow is anomaly packet → situation-specific AI interpretation → deterministic policy → optional event.
- Strong urgent deterministic evidence may create a provisional event immediately; AI cannot hide, downgrade, cancel, or delay it.
- AI receives bounded structured evidence and relevant context, never continuous raw streams or unnecessary identifying data.
- AI output must allow `unknown`, cite valid evidence references, preserve contradictions/limitations, and pass deterministic validation.
- Existing durable event lifecycle, recurrence, priority history, idempotency, tenant isolation, resident memory, calibration, and audit history are extended rather than duplicated.
- Routine context can reduce avoidable non-urgent interruption but never suppress urgent physical evidence.
- Identical fixture input plus policy/model/skill versions must replay to the same decisions.
- Every production behavior follows RED → verify expected failure → GREEN → refactor; tests assert observable behavior with hand-derived expected values.

---

### Task 1: Normalized observations, quality, and aligned fusion

**Files:**
- Create: `backend/app/intelligence/__init__.py`
- Create: `backend/app/intelligence/observations.py`
- Create: `backend/app/intelligence/quality.py`
- Create: `backend/app/intelligence/fusion.py`
- Create: `tests/intelligence/__init__.py`
- Create: `tests/intelligence/test_observations_quality_fusion.py`

**Interfaces:**
- Produces: `QualityClass`, `FeaturePurpose`, `FeatureValue`, `NormalizedObservation`, `FeatureEvidence`, `AlignedFrame`, `quality_allows_detection(feature, purpose)`, `quality_allows_learning(feature, purpose)`, and `align_observations(...)`.
- `FeatureValue.value` is `float | int | bool | str | None`; `None` is required when quality is `UNUSABLE` and forbidden otherwise.
- `align_observations(observations, *, frame_id, window_start, window_end, expected_sources)` returns one immutable `AlignedFrame`, explicitly listing `sources_present`, `sources_missing`, feature evidence, agreements, and contradictions.

- [ ] **Step 1: Write failing contract and fusion tests**

Add tests with fixed UTC timestamps proving: unusable values require `None`; good values require a value and purpose; a feature can be good for movement but unavailable for respiration; only good values learn; missing expected sensors appear in `sources_missing`; contradictory categorical position evidence is preserved instead of averaged; observations outside the target window are rejected.

```python
def test_unusable_feature_cannot_carry_a_numeric_value():
    with pytest.raises(ValueError, match="unusable feature value must be None"):
        FeatureValue("movement_energy", 0.4, "normalized", QualityClass.UNUSABLE, ("stale",), (FeaturePurpose.MOVEMENT,))

def test_alignment_preserves_missing_source_and_position_contradiction():
    frame = align_observations(
        (radar_position("floor_like"), thermal_position("upright_like")),
        frame_id="frame_1",
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        expected_sources=("radar", "thermal", "wifi_csi"),
    )
    assert frame.sources_missing == ("wifi_csi",)
    assert frame.contradictions == ("position_state:radar=floor_like,thermal=upright_like",)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/intelligence/test_observations_quality_fusion.py -q`

Expected: collection fails because `backend.app.intelligence` does not exist.

- [ ] **Step 3: Implement immutable observation and fusion types**

Use `StrEnum`, frozen dataclasses, timezone-aware timestamps, sorted deterministic tuples, and explicit validation. Do not calculate a universal sensor score. Agreement is same-name/same-unit/same-value evidence from independent sources; contradiction is same-name categorical evidence with different values.

- [ ] **Step 4: Verify GREEN and regressions**

Run: `python3 -m pytest tests/intelligence/test_observations_quality_fusion.py tests/monitoring_domain/test_monitoring.py -q`

Expected: all pass with no warnings.

- [ ] **Step 5: Commit**

```bash
git add backend/app/intelligence tests/intelligence
git commit -m "feat: add normalized monitoring evidence foundation"
```

---

### Task 2: Flexible resident context and relevance retrieval

**Files:**
- Modify: `backend/app/domain/feedback.py`
- Modify: `backend/app/contracts/feedback.py`
- Modify: `backend/app/services/resident_controls.py`
- Modify: `backend/app/api/v1/residents.py`
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/mappers.py`
- Create: `backend/app/db/migrations/versions/0005_flexible_resident_context.py`
- Modify: `tests/feedback_domain/test_memory_admin.py`
- Modify: `tests/api/test_resident_controls_api.py`
- Modify: `tests/persistence/test_memory_admin_repositories.py`
- Modify: `tests/persistence/test_migrations.py`

**Interfaces:**
- Extends existing `MemoryEntry` rather than creating another memory store.
- Adds `context_kind: Literal["routine", "habit", "temporary_change", "expected_new_behavior", "general_context"]`, `effective_from`, `effective_until`, `local_time_start`, `local_time_end`, `recurrence_note`, and `flexibility_note`, all optional except `context_kind` which defaults to `general_context` for old data.
- `ResidentMemory.relevant_entries(at, *, context_kinds=())` returns active entries effective at `at`, preserving insertion order; time ranges are soft context and do not filter the result.
- `AddMemoryEntryRequest` and `CorrectMemoryEntryRequest` expose the fields. Corrections copy no field implicitly: the request contains the complete replacement context.

- [ ] **Step 1: Write failing domain, API, persistence, and migration tests**

Prove a variable bathroom routine is returned across different hours, an expired temporary change is excluded, an expected-new-behavior entry survives repository restart with provenance, invalid `effective_until <= effective_from` is rejected, and old stored rows deserialize as `general_context`.

```python
def test_relevant_entries_treat_flexible_routine_as_a_tendency():
    entry = memory_entry(context_kind="routine", description="Bathroom trips vary day to day", flexibility_note="No fixed time")
    memory = ResidentMemory("resident_a", 1, (entry,))
    assert memory.relevant_entries(AT_3_AM) == (entry,)
    assert memory.relevant_entries(AT_3_PM) == (entry,)
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/feedback_domain/test_memory_admin.py tests/api/test_resident_controls_api.py tests/persistence/test_memory_admin_repositories.py tests/persistence/test_migrations.py -q`

Expected: failures name the missing flexible-context fields and migration revision.

- [ ] **Step 3: Extend memory, contracts, service, mapping, and schema**

Use nullable database columns so existing snapshots remain readable. Validate aware datetimes, complete local-time pairs in `HH:MM` form, and effective ordering. Include the new fields in audit payloads and response mapping. Preserve current optimistic concurrency and append-only correction behavior.

- [ ] **Step 4: Verify GREEN and compatibility**

Run: `python3 -m pytest tests/feedback_domain tests/api/test_resident_controls_api.py tests/persistence/test_memory_admin_repositories.py tests/persistence/test_migrations.py tests/api/test_preference_memory_contracts.py -q`

Expected: all pass and existing memory requests without new fields remain valid.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/feedback.py backend/app/contracts/feedback.py backend/app/services/resident_controls.py backend/app/api/v1/residents.py backend/app/db/models.py backend/app/db/mappers.py backend/app/db/migrations/versions/0005_flexible_resident_context.py tests
git commit -m "feat: add flexible resident behavior context"
```

---

### Task 3: Robust personal baseline and controlled new-normal adoption

**Files:**
- Create: `backend/app/intelligence/baseline.py`
- Create: `tests/intelligence/test_baseline.py`

**Interfaces:**
- Consumes: Task 1 `FeatureEvidence`, `FeaturePurpose`, `QualityClass`; existing `MonitoringSnapshot`, `CalibrationProgress`, and Task 2 `MemoryEntry` references.
- Produces: `BaselinePolicy`, `FeatureBaseline`, `BaselineSnapshot`, `LearningGuard`, `NewNormalCandidate`, `build_feature_baseline(...)`, `robust_deviation(...)`, `window_is_learning_eligible(...)`, and `advance_new_normal(...)`.
- `FeatureBaseline` stores median, MAD, IQR, lower/upper empirical quantiles, resolution floor, unit, eligible sample count, and context key.
- Robust deviation denominator is `max(1.4826 * MAD, IQR / 1.349, resolution_floor)`.
- Empirical quantiles use deterministic nearest-rank selection.
- `BaselinePolicy` is versioned and `test_only=True`; its initial fixture values are `minimum_samples=5`, `lower_quantile=0.1`, `upper_quantile=0.9`, and `new_normal_clean_windows=5`.

- [ ] **Step 1: Write failing baseline and learning-guard tests**

Use literal samples `(10.0, 10.0, 11.0, 12.0, 100.0)` and assert median `11.0`, MAD `1.0`, lower quantile `10.0`, upper quantile `100.0`, and a finite robust deviation. Prove away, multi-person, limited/unusable, active candidate, unresolved guard, setup change, and recovery freeze each block learning. Prove an expected new behavior is semantic context immediately but publishes a new numerical snapshot only after five separate clean windows.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/intelligence/test_baseline.py -q`

Expected: failure because `backend.app.intelligence.baseline` does not exist.

- [ ] **Step 3: Implement the transparent baseline engine**

Use only the Python standard library. Return explicit ineligibility reasons. Do not mutate an existing baseline snapshot; publish a new version with `prior_baseline_id` and adoption/context provenance. Setup changes produce a new lineage for affected feature names only.

- [ ] **Step 4: Verify GREEN and calibration compatibility**

Run: `python3 -m pytest tests/intelligence/test_baseline.py tests/calibration_domain/test_calibration.py -q`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/intelligence/baseline.py tests/intelligence/test_baseline.py
git commit -m "feat: add robust personal baseline engine"
```

---

### Task 4: Anomaly episodes and rich evidence packets

**Files:**
- Create: `backend/app/intelligence/anomaly.py`
- Create: `backend/app/intelligence/evidence.py`
- Create: `tests/intelligence/test_anomaly_evidence.py`

**Interfaces:**
- Consumes: Task 1 aligned frames and Task 3 baseline/deviation outputs.
- Produces: `AnomalyState`, `SyntheticAnomalyPolicy`, `FeatureDeviation`, `AnomalyEpisode`, `AnomalyUpdate`, `EvidencePacket`, `advance_episode(...)`, and `build_evidence_packet(...)`.
- Policy fixture values: `start_abs_z=3.0`, `end_abs_z=1.5`, `activation_frames=3`, `recovery_frames=3`, `missing_grace_frames=2`, `test_only=True`, and `policy_version="synthetic_anomaly_v1"`.
- Episode flow is `candidate → active → recovering → closed`; related continuous evidence preserves one anomaly ID and increments immutable packet revisions; post-recovery recurrence uses a new anomaly ID and `recurrence_of`.

- [ ] **Step 1: Write failing state-machine and evidence tests**

Prove two threshold crossings remain a candidate, the third activates it, three sub-end-threshold good frames close it through recovering, a missing frame pauses rather than advances recovery, continuous evidence increments packet revision without changing anomaly ID, and the packet contains exact feature values, unit, quality, baseline statistics, robust z, agreements, contradictions, missing modalities, versions, and explicit unknowns.

```python
def test_acknowledgment_is_not_an_anomaly_input():
    parameters = inspect.signature(advance_episode).parameters
    assert "event_status" not in parameters
    assert "acknowledged" not in parameters
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/intelligence/test_anomaly_evidence.py -q`

Expected: failure because anomaly and evidence modules do not exist.

- [ ] **Step 3: Implement lifecycle, hysteresis, recurrence, and evidence**

Use explicit timestamps and immutable revisions. Missing frames may exceed the grace and mark evidence limited, but cannot count toward recovery. Preserve unknown anomalies rather than requiring a semantic label. Evidence references are stable strings derived from anomaly ID, revision, and feature name.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m pytest tests/intelligence/test_anomaly_evidence.py tests/intelligence/test_baseline.py -q`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/intelligence/anomaly.py backend/app/intelligence/evidence.py tests/intelligence/test_anomaly_evidence.py
git commit -m "feat: add anomaly episodes and evidence packets"
```

---

### Task 5: Monitoring degradation and urgent fall-like fast path

**Files:**
- Create: `backend/app/intelligence/fall_detection.py`
- Create: `backend/app/intelligence/degradation.py`
- Create: `tests/intelligence/test_safety_paths.py`

**Interfaces:**
- Consumes: Task 1 feature evidence and aligned frames.
- Produces: `FallLikeState`, `SyntheticFallPolicy`, `FallLikeAssessment`, `advance_fall_like(...)`, `DegradationKind`, `DegradationAssessment`, and `assess_monitoring_degradation(...)`.
- Synthetic fall fixture values: descent below `-0.8 m/s`, tracked-height drop at least `0.7 m`, low-position evidence, post-transition movement at most `0.15 normalized`, and confirmation within `5 seconds`; all are versioned/test-only and explicitly non-clinical.
- `FallLikeAssessment.urgent_triggered` is true only from valid deterministic evidence; LLM output is not an input.

- [ ] **Step 1: Write failing safety-path tests**

Cover strong radar plus thermal corroboration, radar strong with thermal missing and lower confidence, quick sitting, kneeling, controlled descent, picking something up, intentional lying, stale/frozen signal degradation, device movement/environment shift, and possible-multiple-person attribution limitation. Assert degradation produces an operational assessment rather than a resident anomaly.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/intelligence/test_safety_paths.py -q`

Expected: failure because the safety-path modules do not exist.

- [ ] **Step 3: Implement transparent state machines**

Keep source evidence and contradiction separate. Never average away a contradiction. Return `urgent_triggered=False` for each confounder fixture. Possible-multiple-person may preserve urgent room-level evidence but must include `resident_attribution_uncertain`.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m pytest tests/intelligence/test_safety_paths.py tests/intelligence/test_observations_quality_fusion.py -q`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/intelligence/fall_detection.py backend/app/intelligence/degradation.py tests/intelligence/test_safety_paths.py
git commit -m "feat: add deterministic monitoring safety paths"
```

---

### Task 6: Situation-specific AI skills, context, fake provider, and validation

**Files:**
- Create: `backend/app/ai/__init__.py`
- Create: `backend/app/ai/client.py`
- Create: `backend/app/ai/skills.py`
- Create: `backend/app/ai/context.py`
- Create: `backend/app/ai/validation.py`
- Create: `prompts/monitoring/core.md`
- Create: `prompts/monitoring/fall_like.md`
- Create: `prompts/monitoring/inactivity.md`
- Create: `prompts/monitoring/movement.md`
- Create: `prompts/monitoring/respiration.md`
- Create: `prompts/monitoring/routine_change.md`
- Create: `prompts/monitoring/monitoring_degraded.md`
- Create: `prompts/monitoring/multi_person.md`
- Create: `prompts/monitoring/unknown_anomaly.md`
- Create: `tests/ai/__init__.py`
- Create: `tests/ai/test_monitoring_interpretation.py`

**Interfaces:**
- Consumes: Task 2 relevant resident context and Task 4 `EvidencePacket`.
- Produces: `InterpretationStatus`, `RecommendedDisposition`, `InterpretationRequest`, `InterpretationResult`, `LLMClient` protocol, `DeterministicFakeLLMClient`, `SkillBundle`, `select_skill_bundle(...)`, `build_interpretation_request(...)`, and `validate_interpretation(...)`.
- One request contains the core skill plus exactly one primary situation skill and optional `multi_person` skill. It stores prompt, skill-bundle, retrieval-contract, output-schema, model, and invocation versions.
- Allowed dispositions are `no_action`, `observe`, `awareness`, and `caregiver_event`.

- [ ] **Step 1: Write failing selection, request, fake-provider, and validator tests**

Prove movement evidence selects `core + movement`; ambiguous presence adds `multi_person`; unknown evidence selects `unknown_anomaly`; request JSON excludes raw arrays and unrelated resident entries; fake provider returns deterministic output for the same request; `unknown` is valid; invented evidence refs, described unavailable measurements, diagnostic certainty, omitted contradictions, invalid enum values, and attempted urgent downgrade are rejected with exact validation reasons.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/ai/test_monitoring_interpretation.py -q`

Expected: failure because `backend.app.ai` does not exist.

- [ ] **Step 3: Implement skills and structured interpretation boundary**

Each Markdown skill states its objective, evidence allowed, uncertainty rules, unsupported claims, and output fields. Load skills by an explicit name-to-path registry rooted at `prompts/monitoring`; reject unknown names and path traversal. The fake provider is the only Phase 5 provider implementation and performs no network call.

- [ ] **Step 4: Verify GREEN and privacy contract**

Run: `python3 -m pytest tests/ai/test_monitoring_interpretation.py -q`

Expected: all pass; serialized requests contain no raw sensor arrays or resident display names.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ai prompts/monitoring tests/ai
git commit -m "feat: add monitoring AI skill boundary"
```

---

### Task 7: Deterministic disposition, event bridge, cooldown, and orchestration

**Files:**
- Create: `backend/app/intelligence/policy.py`
- Create: `backend/app/intelligence/orchestration.py`
- Modify: `backend/app/domain/events.py`
- Create: `tests/intelligence/test_policy_orchestration.py`
- Modify: `tests/event_domain/test_events.py`

**Interfaces:**
- Consumes: Tasks 3–6 outputs and existing `EventStore`/`MonitoringEvent`.
- Produces: `PolicyDisposition`, `SyntheticDispositionPolicy`, `DispositionDecision`, `MonitoringIntelligenceEngine`, `IntelligenceResult`, and `EventAttentionPolicy`.
- Policy order is system/data integrity → presence/attribution → urgent trigger → anomaly strength/persistence/calibration → validated interpretation → final disposition.
- `MonitoringIntelligenceEngine.process_frame(...)` returns observation/baseline/anomaly/evidence/interpretation/decision/event references in one result without hiding intermediate state.
- Event bridge idempotency key is `anomaly_id:packet_revision:policy_version`; repeated processing updates the same related active event and never duplicates it.
- Event acknowledgment creates an attention cooldown recommendation; continuing evidence updates the event, material priority escalation overrides cooldown, and event state never enters anomaly lifecycle logic.

- [ ] **Step 1: Write failing policy and orchestration tests**

Prove: normal evidence returns `NO_ACTION`; variable bathroom/away context returns awareness or no action; a sustained non-urgent anomaly invokes the fake LLM before policy; invalid/unavailable LLM uses objective fallback; urgent fall-like evidence creates an event without an LLM result; routine context never suppresses urgent evidence; duplicate packet processing is idempotent; continuing acknowledged evidence updates one event; escalation overrides cooldown; recovery closes the anomaly without resolving the event; recurrence after recovery creates a linked event.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/intelligence/test_policy_orchestration.py tests/event_domain/test_events.py -q`

Expected: failures name the missing policy/orchestration types and attention behavior.

- [ ] **Step 3: Implement policy, bridge, and attention semantics**

Use existing `EventPriority` and `EventStore.record_signal`. Add only the event metadata required for `source_anomaly_id`, latest evidence revision, attention suppression-until, and provisional-urgent status, with backward-compatible defaults. Preserve the existing lifecycle transition rules and resolved-event immutability.

- [ ] **Step 4: Verify GREEN and existing event behavior**

Run: `python3 -m pytest tests/intelligence/test_policy_orchestration.py tests/event_domain tests/toy_scenario -q`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/intelligence/policy.py backend/app/intelligence/orchestration.py backend/app/domain/events.py tests/intelligence/test_policy_orchestration.py tests/event_domain/test_events.py
git commit -m "feat: connect monitoring intelligence to caregiver events"
```

---

### Task 8: Durable intelligence repositories and restart replay

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/mappers.py`
- Modify: `backend/app/db/repositories.py`
- Create: `backend/app/db/intelligence_mappers.py`
- Create: `backend/app/db/intelligence_repositories.py`
- Create: `backend/app/db/migrations/versions/0006_monitoring_intelligence.py`
- Create: `tests/persistence/test_intelligence_repositories.py`
- Modify: `tests/persistence/test_migrations.py`
- Modify: `tests/persistence/test_restart_durability.py`

**Interfaces:**
- Persists immutable baseline snapshots/dimensions, anomaly episodes/evidence revisions, interpretation request/result/version metadata, disposition decisions, event-bridge idempotency records, and new-normal adoption provenance.
- Repository methods are tenant-scoped: `save_baseline`, `latest_baseline`, `save_anomaly_revision`, `latest_anomaly`, `save_interpretation`, `find_interpretation`, `save_disposition`, and `find_event_bridge`.
- Duplicate immutable IDs with different payloads raise `ConcurrentUpdateError`; identical writes return the existing record.

- [ ] **Step 1: Write failing schema, repository, tenant, idempotency, and restart tests**

Persist one complete intelligence result, close the session, reopen the database, and assert the same versions, evidence refs, interpretation provenance, disposition, and event bridge are returned. Prove cross-tenant reads return no object and payload-changing duplicate writes fail.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/persistence/test_intelligence_repositories.py tests/persistence/test_migrations.py tests/persistence/test_restart_durability.py -q`

Expected: failures name missing tables/repositories and migration revision `0006`.

- [ ] **Step 3: Implement append-only persistence**

Store structured packet/request/result bodies as canonical JSON while keeping tenant, resident, room, anomaly, revision, baseline, event, status, and timestamp columns queryable. Sort keys and use compact separators for canonical comparison. Add backward-compatible persistence mapping for Task 7 event metadata. Do not persist continuous raw arrays.

- [ ] **Step 4: Verify GREEN and full persistence regression**

Run: `python3 -m pytest tests/persistence -q`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/app/db/mappers.py backend/app/db/repositories.py backend/app/db/intelligence_mappers.py backend/app/db/intelligence_repositories.py backend/app/db/migrations/versions/0006_monitoring_intelligence.py tests/persistence
git commit -m "feat: persist monitoring intelligence decisions"
```

---

### Task 9: Complete normalized-fixture replay, metrics, and founder checkpoint

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/monitoring/__init__.py`
- Create: `evals/monitoring/scenarios.py`
- Create: `evals/monitoring/replay.py`
- Create: `evals/monitoring/metrics.py`
- Create: `backend/app/checkpoints/monitoring_intelligence.py`
- Create: `tests/evals/__init__.py`
- Create: `tests/evals/test_monitoring_replay.py`
- Create: `docs/PHASE_5_BACKEND_REVIEW.md`
- Modify: `docs/CURRENT_STAGE.md`
- Modify: `docs/PHASE_GATES.md`
- Modify: `docs/COFOUNDER_BACKEND_REVIEW.md`

**Interfaces:**
- `python3 -m backend.app.checkpoints.monitoring_intelligence` runs the canonical founder walkthrough and exits nonzero on an invariant failure.
- `python3 -m evals.monitoring.replay --format json` emits stable JSON with policy versions and: meaningful anomaly recall, false packets/resident-day, false events/resident-day, missed meaningful events, candidate/packet/event latency, duplicate-event rate, event-duration error, baseline contamination, monitoring-state durations, interpretation validity, supported/unsupported claims, and replay reproducibility.
- Scenario IDs are stable and include normal variation, random bathroom/away, sleep/reading stillness, routines/temporary changes, visitors, movement/repetition, inactivity, fall-like plus confounders, respiration quality, unknown anomaly, missing/stale/frozen/contradictory sensors, setup change, pre-entered new behavior, post-event new behavior, continuing acknowledged anomaly, recurrence, and LLM failure/invalidity.

- [ ] **Step 1: Write failing replay and metric tests**

Assert the canonical suite includes every named scenario, ordinary scenarios produce no caregiver event except explicit awareness, meaningful scenarios are captured, baseline contamination is exactly zero, duplicate-event rate is zero, invalid AI claims count as rejected rather than supported, and two runs produce byte-identical canonical JSON except an explicitly absent wall-clock field.

- [ ] **Step 2: Verify RED**

Run: `python3 -m pytest tests/evals/test_monitoring_replay.py -q`

Expected: failure because the evaluation package and checkpoint do not exist.

- [ ] **Step 3: Implement fixtures, runner, metrics, and checkpoint**

All fixture values are deterministic and visibly synthetic. Use injected timestamps and IDs. The checkpoint prints a plain-language flow: what stayed quiet, what opened an internal anomaly, when AI ran, what urgent path bypassed AI, what caregiver event resulted, how acknowledgment/cooldown behaved, and how feedback/new-normal learning remained controlled.

- [ ] **Step 4: Write the founder review document**

Record what works, the exact flow, test/eval commands, scenario matrix, measured synthetic results, limitations, deferred Phase 6 edge ingestion, deferred real-provider integration, and the frontend handoff fields. Do not claim clinical accuracy.

- [ ] **Step 5: Verify GREEN and the complete repository**

Run:

```bash
python3 -m pytest -q
python3 -m backend.app.checkpoints.monitoring_intelligence
python3 -m evals.monitoring.replay --format json
git diff --check
```

Expected: all tests pass; both commands exit zero; replay JSON is deterministic; no whitespace errors.

- [ ] **Step 6: Commit**

```bash
git add evals backend/app/checkpoints/monitoring_intelligence.py tests/evals docs/PHASE_5_BACKEND_REVIEW.md docs/CURRENT_STAGE.md docs/PHASE_GATES.md docs/COFOUNDER_BACKEND_REVIEW.md
git commit -m "feat: complete Phase 5 monitoring intelligence replay"
```
