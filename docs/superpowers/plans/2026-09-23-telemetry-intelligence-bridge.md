# Telemetry Intelligence Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Receive Mahin-shaped radar, thermal, and Wi-Fi CSI telemetry and carry it durably through assignment, normalization, fusion, replay, and the existing monitoring-intelligence/event system.

**Architecture:** Add an authenticated ingestion boundary and immutable telemetry store, then keep every hardware-specific field inside source normalizers. One HTTP telemetry list is one atomic capture cycle; exact retries are idempotent. Valid assignment-scoped observations become an existing `AlignedFrame`, while persistence and replay surround the already-built baseline/anomaly/AI/event engine.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite tests/Postgres-compatible schema, pytest, existing monitoring intelligence and scripted AI evaluation clients; no new external queue, SDK, or signal-processing dependency.

**Spec:** `docs/superpowers/specs/2026-09-23-telemetry-intelligence-bridge-design.md`

## Global Constraints

- Hardware owns raw/vendor parsing and per-source measurement extraction; cloud owns assignment, fusion, baselines, anomaly/event logic, AI, and learning.
- Current Mahin envelopes remain accepted; `stream_id` is optional and defaults to `legacy`.
- One telemetry-list POST is one atomic capture cycle even when producer `transport.batch_id` values differ.
- Missing/unavailable values are omitted or explicitly unusable; never zero-fill, impute, or forward-fill.
- Host-derived `/v1/assessments` never controls product anomalies or events.
- V1 assigns one resident per monitored room and never guesses attribution during missing/conflicting assignment or possible multi-person presence.
- No clinical thresholds or diagnostic claims; initial baseline/anomaly policies remain explicitly synthetic/test-only.
- Ingestion commits before intelligence processing so accepted packets survive later failures.
- No frontend, firmware, deployment, production-PKI, or live-model-gate changes in this branch.
- Every production behavior is introduced through a witnessed red-green-refactor test cycle.

## Review Focus

- Exact retry after success returns the original batch and creates no new packet, frame, analysis, or event.
- Same packet identity with different content is a conflict, not a retry.
- Tenant/room mismatch or missing active assignment creates no resident-specific observation or event.
- A new `stream_id` may restart sequence numbering; a same-stream reset is stale.
- Missing/low-quality modalities never become invented zeros or eligible baseline samples.

---

### Task 1: Freeze the Versioned Ingestion Contract

**Files:**
- Create: `backend/app/contracts/ingestion.py`
- Modify: `backend/app/contracts/__init__.py`
- Modify: `backend/app/intelligence/observations.py`
- Modify: `docs/DATA_CONTRACT.md`
- Test: `tests/api/test_ingestion_contracts.py`
- Create: `tests/fixtures/edge_telemetry/mahin_capture_v1.json`

**Interfaces:**
- Consumes: Mahin's current envelope fields and three source payload formats.
- Produces: `EdgeTelemetryEnvelope`, `TelemetryCaptureRequest`, `DeviceHeartbeatRequest`, `TelemetryIngestResponse`, and `FeaturePurpose.PHYSIOLOGY`.

- [ ] **Step 1: Add a current-hardware-shape fixture**

Copy the emitted JSON shape, not hardware algorithms: three envelopes in one
list, different producer batch IDs, absent `stream_id`, nullable clocks,
omitted unavailable readings, and optional `quality_reasons`.

- [ ] **Step 2: Write failing contract tests**

```python
def test_current_mahin_capture_parses_without_rewrite() -> None:
    parsed = TelemetryCaptureRequest.model_validate_json(FIXTURE.read_text())
    assert [item.source for item in parsed.root] == ["radar", "thermal", "wifi_csi"]
    assert all(item.stream_id == "legacy" for item in parsed.root)


def test_null_measurement_is_rejected_but_omission_is_valid() -> None:
    with pytest.raises(ValidationError):
        EdgeTelemetryEnvelope.model_validate(
            radar_envelope(payload={"heart_rate_bpm": None})
        )
```

Also pin source/format mismatch, non-finite numbers, score ranges, positive
sequence, unique sources per capture, homogeneous tenant/device/room, payload
size, and unknown top-level fields.

- [ ] **Step 3: Verify red**

Run: `python3 -m pytest tests/api/test_ingestion_contracts.py -q`
Expected: FAIL because the ingestion contracts do not exist.

- [ ] **Step 4: Implement the strict Pydantic contracts**

Use bounded strings/lists, finite-number checks, source-specific payload
validation, `extra="forbid"`, and legacy normalization for absent `stream_id`.

- [ ] **Step 5: Update shared vocabulary and contract docs**

Add `FeaturePurpose.PHYSIOLOGY`; document `stream_id`, `quality_reasons`,
request-level capture grouping, and revised idempotency identity.

- [ ] **Step 6: Verify green and commit**

```bash
python3 -m pytest tests/api/test_ingestion_contracts.py tests/intelligence/test_observations_quality_fusion.py -q
git add backend/app/contracts backend/app/intelligence/observations.py tests/api/test_ingestion_contracts.py tests/fixtures/edge_telemetry docs/DATA_CONTRACT.md
git commit -m "feat(ingest): freeze edge telemetry contract"
```

### Task 2: Add Durable Telemetry and Replay Storage

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/app/db/telemetry_mappers.py`
- Create: `backend/app/db/telemetry_repositories.py`
- Create: `backend/app/db/migrations/versions/0008_edge_telemetry_ingestion.py`
- Test: `tests/persistence/test_telemetry_repositories.py`
- Modify: `tests/persistence/test_migrations.py`

**Interfaces:**
- Consumes: validated `TelemetryCaptureRequest` and heartbeat.
- Produces: immutable batch/packet/observation/frame records plus `TelemetryRepository.save_capture()`, `.mark_processed()`, `.pending_batches()`, and `HeartbeatRepository.record()`.

- [ ] **Step 1: Write failing idempotency and durability tests**

```python
def test_exact_capture_retry_returns_original_batch(session) -> None:
    first = repository.save_capture(capture, received_at=NOW)
    second = repository.save_capture(capture, received_at=LATER)
    assert second.batch_id == first.batch_id
    assert second.duplicate is True
    assert count_packets(session) == 3


def test_changed_duplicate_conflicts(session) -> None:
    repository.save_capture(capture, received_at=NOW)
    with pytest.raises(ConcurrentUpdateError):
        repository.save_capture(changed_same_identity, received_at=LATER)
```

Also pin new-stream reset, same-stream stale sequence, accepted sequence gap,
atomic rollback, pending ordering, stored normalized observations/frames, and
heartbeat retry.

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest tests/persistence/test_telemetry_repositories.py -q`
Expected: FAIL because rows and repository do not exist.

- [ ] **Step 3: Implement migration, rows, mappers, and repositories**

Add capture-batch, telemetry-packet, normalized-observation, fused-frame, and
heartbeat-identity tables. Canonicalize JSON before hashing. Reconcile exact
duplicates, reject conflicts/stale streams, and retain bounded failure state.

- [ ] **Step 4: Verify green and commit**

```bash
python3 -m pytest tests/persistence/test_telemetry_repositories.py tests/persistence/test_migrations.py -q
git add backend/app/db tests/persistence
git commit -m "feat(ingest): persist replayable telemetry batches"
```

### Task 3: Resolve Assignment and Normalize Every Source

**Files:**
- Create: `backend/app/ingestion/__init__.py`
- Create: `backend/app/ingestion/assignment.py`
- Create: `backend/app/ingestion/normalizers.py`
- Modify: `backend/app/db/device_repositories.py`
- Test: `tests/ingestion/test_assignment.py`
- Test: `tests/ingestion/test_normalizers.py`

**Interfaces:**
- Consumes: stored envelope plus server-resolved assignment.
- Produces: `resolve_monitoring_assignment(...) -> MonitoringAssignment` and `normalize_envelope(...) -> NormalizedObservation`.

- [ ] **Step 1: Write failing assignment tests**

```python
def test_resident_comes_from_server_assignment(session) -> None:
    assignment = resolve_monitoring_assignment(
        session, "tenant_demo", "device_room_214", "room_214"
    )
    assert assignment.resident_id == "resident_demo_a"


def test_declared_room_mismatch_blocks_processing(session) -> None:
    with pytest.raises(AssignmentUnavailableError):
        resolve_monitoring_assignment(
            session, "tenant_demo", "device_room_214", "room_other"
        )
```

Pin missing device-room assignment, missing room-resident assignment, wrong
tenant, and conflicting assignment state.

- [ ] **Step 2: Write failing source-normalizer tests**

```python
def test_radar_maps_to_neutral_features() -> None:
    observation = normalize_envelope(radar, assignment, NOW)
    assert feature(observation, "respiratory_rate").unit == "rpm"
    assert feature(observation, "heart_rate").purposes == (FeaturePurpose.PHYSIOLOGY,)


def test_missing_vital_is_not_invented() -> None:
    observation = normalize_envelope(radar_without_vitals, assignment, NOW)
    assert "heart_rate" not in {item.name for item in observation.features}
```

Pin thermal near-floor extraction, CSI mapping, quality reasons, empty/unusable
payload, deterministic IDs, and optional future posture fields.

- [ ] **Step 3: Verify red**

Run: `python3 -m pytest tests/ingestion/test_assignment.py tests/ingestion/test_normalizers.py -q`
Expected: FAIL because ingestion modules do not exist.

- [ ] **Step 4: Implement one isolated normalizer per format**

No vendor imports. Preserve source limitations, keep unrelated present fields
usable, and derive observation IDs from immutable packet identity plus processor
version.

- [ ] **Step 5: Verify green and commit**

```bash
python3 -m pytest tests/ingestion tests/intelligence/test_observations_quality_fusion.py -q
git add backend/app/ingestion backend/app/db/device_repositories.py tests/ingestion
git commit -m "feat(ingest): normalize assigned sensor evidence"
```

### Task 4: Expose Authenticated Telemetry and Heartbeat APIs

**Files:**
- Modify: `backend/app/config.py`
- Modify: `.env.example`
- Create: `backend/app/services/telemetry_ingestion.py`
- Create: `backend/app/api/v1/ingestion.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/api/dependencies.py`
- Test: `tests/api/test_ingestion_api.py`
- Modify: `tests/api/test_openapi_contract.py`

**Interfaces:**
- Consumes: bearer-authenticated capture/heartbeat requests.
- Produces: `POST /v1/ingest/telemetry`, `POST /v1/ingest/heartbeat`, and an injected post-commit processor callback.

- [ ] **Step 1: Write failing route and auth tests**

```python
def test_mahin_capture_is_accepted(client, ingest_headers) -> None:
    response = client.post("/v1/ingest/telemetry", json=fixture(), headers=ingest_headers)
    assert response.status_code == 202
    assert response.json()["accepted"] == 3


def test_exact_network_retry_is_idempotent(client, ingest_headers) -> None:
    first = post_capture(client, ingest_headers)
    second = post_capture(client, ingest_headers)
    assert second.json()["batch_id"] == first.json()["batch_id"]
    assert second.json()["duplicate"] is True
```

Pin missing/wrong key, absent runtime configuration, mixed capture, body/batch
limits, conflict, assignment block, heartbeat health, and secret-free errors.

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest tests/api/test_ingestion_api.py -q`
Expected: FAIL with 404.

- [ ] **Step 3: Implement auth, routes, and heartbeat mapping**

Use constant-time comparison and no committed key. Store/commit accepted
telemetry before processing. Map heartbeat status/backlog/sources/assignment to
existing device-health history without duplicating retry records.

- [ ] **Step 4: Verify green and commit**

```bash
python3 -m pytest tests/api/test_ingestion_api.py tests/api/test_openapi_contract.py tests/persistence/test_device_repositories.py tests/persistence/test_telemetry_repositories.py -q
git add .env.example backend/app/config.py backend/app/services/telemetry_ingestion.py backend/app/api tests/api
git commit -m "feat(ingest): receive authenticated device telemetry"
```

### Task 5: Fuse Captures and Connect Monitoring Intelligence

**Files:**
- Create: `backend/app/services/telemetry_processing.py`
- Modify: `backend/app/services/monitoring_processing.py`
- Modify: `backend/app/intelligence/orchestration.py`
- Modify: `backend/app/main.py`
- Test: `tests/integration/test_edge_telemetry_pipeline.py`
- Modify: `tests/integration/test_persistent_multi_agent_pipeline.py`

**Interfaces:**
- Consumes: durable pending capture and injected `MonitoringIntelligenceEngine`.
- Produces: `TelemetryProcessingCoordinator.process_batch(batch_id)`, `.drain_pending(limit)`, stored observations/frame, and optional `IntelligenceResult`.

- [ ] **Step 1: Write failing capture-to-frame test**

```python
def test_capture_is_normalized_fused_and_processed(client, repository) -> None:
    response = post_mahin_capture(client)
    batch = repository.get_batch(response.json()["batch_id"])
    assert batch.processing_state == "processed"
    assert set(batch.frame.sources_present) == {"radar", "thermal", "wifi_csi"}
```

Pin missing-source degradation, assignment block with no resident frame,
different producer batch IDs still becoming one frame, and deterministic frame
identity.

- [ ] **Step 2: Write failing restart/event test**

```python
def test_restart_replay_does_not_duplicate_event(database_url) -> None:
    event_id = run_scripted_device_shaped_anomaly(database_url)
    restart_and_drain(database_url)
    assert event_ids(database_url) == [event_id]
```

Seed an established synthetic baseline, inject the existing scripted
multi-agent client, post normal then anomalous captures, and read the event
through the existing API. Pin processing failure remains durable/replayable.

- [ ] **Step 3: Verify red**

Run: `python3 -m pytest tests/integration/test_edge_telemetry_pipeline.py -q`
Expected: FAIL because the coordinator does not exist.

- [ ] **Step 4: Implement processing and restart restoration**

Resolve assignment, normalize, persist observations, align expected sources,
persist frame, load current baseline/memory/status, and call the existing
persistent engine. Add a validated `restore_episode()` boundary parallel to
existing analysis-checkpoint restoration.

- [ ] **Step 5: Keep missing baseline explicit**

Without an established numerical baseline, store the frame as `calibrating`
and create no ordinary anomaly. Do not invent automatic production calibration
before real-sensor validation.

- [ ] **Step 6: Verify green and commit**

```bash
python3 -m pytest tests/integration/test_edge_telemetry_pipeline.py tests/integration/test_persistent_multi_agent_pipeline.py tests/intelligence tests/ai -q
git add backend/app/services/telemetry_processing.py backend/app/services/monitoring_processing.py backend/app/intelligence/orchestration.py backend/app/main.py tests/integration
git commit -m "feat(ingest): connect telemetry to monitoring intelligence"
```

### Task 6: Add Device-Shaped Replay and Evaluation

**Files:**
- Create: `evals/telemetry/__init__.py`
- Create: `evals/telemetry/scenarios.py`
- Create: `evals/telemetry/replay.py`
- Create: `evals/telemetry/cli.py`
- Create: `tests/evals/test_edge_telemetry_replay.py`
- Create: `docs/TELEMETRY_PIPELINE_TEST_REPORT.md`

**Interfaces:**
- Consumes: production ingestion boundary; truth stays outside envelopes.
- Produces: `python3 -m evals.telemetry.cli --output <dir>`, JSON artifacts, and a stable Markdown report.

- [ ] **Step 1: Write failing coverage and truth-separation tests**

```python
def test_required_scenario_families_exist() -> None:
    assert REQUIRED_FAMILIES <= {scenario.family for scenario in scenarios()}


def test_truth_never_enters_production_envelope() -> None:
    for scenario in scenarios():
        assert "expected" not in json.dumps(scenario.capture_payloads)
```

Pin deterministic replay, normal false events, supported anomaly recall,
assignment blocks, source ablations, retries, conflicts, stream restart, and
low-quality baseline exclusion.

- [ ] **Step 2: Verify red**

Run: `python3 -m pytest tests/evals/test_edge_telemetry_replay.py -q`
Expected: FAIL because `evals.telemetry` does not exist.

- [ ] **Step 3: Implement at least 48 deterministic cases and metrics**

Cover normal variation, away/return, bathroom-like absence, unusual movement,
inactivity, physiological deviation, optional posture/fall-like evidence,
source ablations, degraded quality, retry/conflict/stale/gap/new-stream,
assignment failure, recovery, and recurrence. Record ingest, processing,
assignment, feature, replay, event, false-event, recall, and latency metrics.

- [ ] **Step 4: Run twice for reproducibility**

```bash
python3 -m evals.telemetry.cli --output output/telemetry-eval-a
python3 -m evals.telemetry.cli --output output/telemetry-eval-b
python3 -m pytest tests/evals/test_edge_telemetry_replay.py -q
```

Expected: stable result content apart from explicitly excluded runtime fields.

- [ ] **Step 5: Commit the evaluation checkpoint**

```bash
git add evals/telemetry tests/evals/test_edge_telemetry_replay.py docs/TELEMETRY_PIPELINE_TEST_REPORT.md
git commit -m "test(ingest): prove telemetry pipeline with replay"
```

### Task 7: Finish Handoff and Whole-Branch Verification

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/BUILD_PLAN.md`
- Modify: `docs/CURRENT_STAGE.md`
- Create: `docs/HARDWARE_BACKEND_HANDOFF.md`
- Create: `docs/TELEMETRY_BACKEND_REVIEW.md`
- Modify: `docs/COFOUNDER_BACKEND_REVIEW.md`

**Interfaces:**
- Consumes: verified implementation and evaluation results.
- Produces: plain-English founder/hardware/reviewer handoff and honest phase state.

- [ ] **Step 1: Document the exact hardware/backend socket**

State payload formats, auth, optional stream ID, request grouping, retry rules,
assignment behavior, ignored host assessments, optional future posture fields,
and Mahin's local run command.

- [ ] **Step 2: Update stage documents honestly**

Mark only proven ingestion/normalization/replay items complete. Keep frontend
real-client wiring, live-model gate, real-hardware calibration, production
credentials, and deployment visibly open.

- [ ] **Step 3: Run focused and complete verification**

```bash
python3 -m pytest -q tests/api/test_ingestion_contracts.py tests/api/test_ingestion_api.py tests/ingestion tests/persistence/test_telemetry_repositories.py tests/integration/test_edge_telemetry_pipeline.py tests/evals/test_edge_telemetry_replay.py
python3 -m pytest -q
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q backend evals tests
python3 -m pytest tests/persistence/test_migrations.py -q
graphify update .
git diff --check
git status --short
```

Expected: all tests pass, compilation succeeds, graph is current, no whitespace
errors, and only intended files are modified. Report exact counts and the known
FastAPI/httpx deprecation warning separately.

- [ ] **Step 4: Commit the final documentation checkpoint**

```bash
git add docs graphify-out
git commit -m "docs(ingest): publish telemetry bridge handoff"
```

## Plan Self-Review

- **Spec coverage:** Tasks 1–7 cover current hardware compatibility, optional
  stream identity, authentication, assignment, durability, normalization,
  fusion, existing intelligence connection, heartbeat health, replay, failure
  semantics, evaluation, and handoff.
- **Intentional gap:** automatic production baseline calibration is not invented
  before real-sensor validation. Established baselines feed the connected
  engine; otherwise frames are explicitly calibrating.
- **Placeholder scan:** no TBD/TODO or undefined implementation step remains.
- **Type consistency:** contract, repository, normalizer, and coordinator names
  remain stable across tasks.
- **Review focus:** exact retry, conflict, assignment block, stream restart, and
  missing/low-quality evidence each have an explicit owning test.
