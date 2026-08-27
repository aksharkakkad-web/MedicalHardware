# Phase 2 Checkpoint A Status and Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and expose resident monitoring state, awareness history, calibration progress, and selective setup-change recalibration through the real Product API.

**Architecture:** Extend the existing pure monitoring/calibration domain with append-only SQLAlchemy records and separate tenant-scoped repositories. Add focused response contracts and resident routes; keep the existing event/query modules small. Setup changes run through the existing idempotency and audit transaction pattern.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite test runtime, PostgreSQL-compatible schema, pytest/unittest.

**Spec:** `docs/superpowers/specs/2026-08-27-phase2-backend-readiness-design.md`

## Global Constraints

- All public objects and mutation bodies use `schema_version: "1.0"`.
- All public timestamps are aware, explicitly UTC, and serialize with `Z`.
- Resident-away is awareness history, not a warning event.
- Away, possible-multi-person, low-quality, unavailable, concerning, and unresolved windows never advance calibration.
- Setup changes reset only affected dimensions while preserving resident history and semantic memory.
- Synthetic quality/calibration policies remain marked test-only and are not clinical rules.
- All reads and writes are tenant-scoped; cross-tenant IDs behave like missing IDs.
- Mutations are atomic, idempotent, audited, and optimistic-concurrency safe.
- Do not edit frontend applications or simulator fixtures in this checkpoint.

---

### Task 1: Freeze the Checkpoint A Product Contract

**Files:**
- Create: `backend/app/contracts/status.py`
- Modify: `backend/app/contracts/__init__.py`
- Modify: `docs/DATA_CONTRACT.md`
- Test: `tests/api/test_status_contracts.py`

**Interfaces:**
- Consumes: `ContractModel`, `RequestContractModel`, `UTCDateTime`, `PresenceState`, `MonitoringState`, `MonitoringReason`, and `BaselineStatus`.
- Produces: `ResidentStatusResponse`, `AwarenessTimelineResponse`, `CalibrationResponse`, and `SetupChangeRequest` used by Tasks 4–6.

- [x] **Step 1: Write failing strict-contract tests**

Create tests that validate exact fields, reject missing/wrong schema versions,
reject non-UTC timestamps, reject unknown fields, and verify nested objects also
carry `schema_version`:

```python
def test_setup_change_requires_version_utc_and_known_dimensions() -> None:
    request = SetupChangeRequest.model_validate(
        {
            "schema_version": "1.0",
            "reason": "device_moved",
            "affected_dimensions": ["movement"],
            "changed_at": "2026-08-24T22:00:00Z",
            "expected_calibration_version": 1,
        }
    )
    assert request.reason == "device_moved"

    with pytest.raises(ValidationError):
        SetupChangeRequest.model_validate(
            {
                "reason": "device_moved",
                "affected_dimensions": ["movement"],
                "changed_at": "2026-08-24T22:00:00Z",
                "expected_calibration_version": 1,
            }
        )
```

- [x] **Step 2: Run the contract tests and verify RED**

Run: `python3 -m pytest -q tests/api/test_status_contracts.py`

Expected: collection fails because `backend.app.contracts.status` does not
exist.

- [x] **Step 3: Implement the strict public models**

Create focused Pydantic models with these exact public fields:

```python
class CalibrationDimensionResponse(ContractModel):
    dimension: str
    status: BaselineStatus
    eligible_windows: int
    excluded_windows: int


class SetupChangeResponse(ContractModel):
    previous_setup_version: str
    new_setup_version: str
    affected_dimensions: list[str]
    reason: str
    actor_id: str
    changed_at: UTCDateTime


class CalibrationResponse(ContractModel):
    resident_id: str
    version: int
    recorded_at: UTCDateTime
    setup_version: str
    status: BaselineStatus
    eligible_windows: int
    excluded_windows: int
    reason: str
    prior_setup_versions: list[str]
    dimensions: list[CalibrationDimensionResponse]
    setup_changes: list[SetupChangeResponse]


class MonitoringStatusResponse(ContractModel):
    resident_id: str
    room_id: str
    observed_at: UTCDateTime
    monitoring_state: MonitoringState
    presence_state: PresenceState
    baseline_learning_allowed: bool
    resident_measurements_allowed: bool
    reasons: list[MonitoringReason]
    quality_policy_version: str
    quality_policy_test_only: bool


class ResidentStatusResponse(ContractModel):
    resident_id: str
    room_id: str
    monitoring: MonitoringStatusResponse
    calibration: CalibrationResponse


class AwarenessTimelineResponse(ContractModel):
    resident_id: str
    items: list[MonitoringStatusResponse]


class SetupChangeRequest(RequestContractModel):
    reason: str
    affected_dimensions: list[str]
    changed_at: UTCDateTime
    expected_calibration_version: int
```

Require nonblank reason/dimensions, unique dimensions, and a non-negative
expected version. Response list fields remain ordered and never use sets.

- [x] **Step 4: Document exact JSON examples and semantics**

Add a "Phase 2 Checkpoint A" subsection to `docs/DATA_CONTRACT.md` containing
the four paths, exact request/response examples, awareness ordering, and the
rule that timestamps and policies are synthetic/test-only where applicable.

- [x] **Step 5: Run contract and full contract suites**

Run:

```bash
python3 -m pytest -q tests/api/test_status_contracts.py tests/api/test_contracts.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

Expected: all pass.

- [x] **Step 6: Commit Task 1**

```bash
git add backend/app/contracts docs/DATA_CONTRACT.md tests/api/test_status_contracts.py
git commit -m "feat: freeze resident status and calibration contracts"
```

---

### Task 2: Add Append-Only Status and Calibration Persistence

**Files:**
- Create: `backend/app/db/migrations/versions/0002_status_calibration.py`
- Modify: `backend/app/db/models.py`
- Modify: `tests/persistence/test_migrations.py`
- Test: `tests/persistence/test_status_schema.py`

**Interfaces:**
- Consumes: existing tenant/resident/room composite ownership keys.
- Produces: `MonitoringStatusSnapshotRow`, `CalibrationSnapshotRow`, and `MonitoringSetupChangeRow` used by Tasks 3–6.

- [x] **Step 1: Write failing migration and ownership tests**

Tests must prove:

```python
EXPECTED_CHECKPOINT_A_TABLES = {
    "monitoring_status_snapshots",
    "calibration_snapshots",
    "monitoring_setup_changes",
}


def test_status_rows_cannot_reference_another_tenants_resident_or_room(...):
    with pytest.raises(IntegrityError):
        connection.execute(cross_tenant_status_insert)


def test_calibration_versions_are_unique_per_tenant_resident(...):
    with pytest.raises(IntegrityError):
        connection.execute(duplicate_version_insert)
```

Also upgrade from revision `0001_product_backbone` to `head`, downgrade to
`0001_product_backbone`, and verify the original tables remain intact.

- [x] **Step 2: Run migration tests and verify RED**

Run: `python3 -m pytest -q tests/persistence/test_migrations.py tests/persistence/test_status_schema.py`

Expected: the three new tables/revision are absent.

- [x] **Step 3: Add ORM rows**

Implement these durable shapes:

```python
class MonitoringStatusSnapshotRow(Base):
    __tablename__ = "monitoring_status_snapshots"
    monitoring_status_id: Mapped[int]
    tenant_id: Mapped[str]
    resident_id: Mapped[str]
    room_id: Mapped[str]
    observed_at: Mapped[datetime]
    monitoring_state: Mapped[str]
    presence_state: Mapped[str]
    baseline_learning_allowed: Mapped[bool]
    resident_measurements_allowed: Mapped[bool]
    reasons: Mapped[list[str]]
    quality_policy_version: Mapped[str]
    quality_policy_test_only: Mapped[bool]


class CalibrationSnapshotRow(Base):
    __tablename__ = "calibration_snapshots"
    calibration_snapshot_id: Mapped[int]
    tenant_id: Mapped[str]
    resident_id: Mapped[str]
    version: Mapped[int]
    recorded_at: Mapped[datetime]
    setup_version: Mapped[str]
    status: Mapped[str]
    eligible_windows: Mapped[int]
    excluded_windows: Mapped[int]
    reason: Mapped[str]
    prior_setup_versions: Mapped[list[str]]
    dimension_progress: Mapped[list[dict[str, object]]]


class MonitoringSetupChangeRow(Base):
    __tablename__ = "monitoring_setup_changes"
    monitoring_setup_change_id: Mapped[int]
    tenant_id: Mapped[str]
    resident_id: Mapped[str]
    calibration_version: Mapped[int]
    previous_setup_version: Mapped[str]
    new_setup_version: Mapped[str]
    affected_dimensions: Mapped[list[str]]
    reason: Mapped[str]
    actor_id: Mapped[str]
    changed_at: Mapped[datetime]
```

Use composite tenant/resident and tenant/room foreign keys. Add unique
constraints for `(tenant_id, resident_id, observed_at)`,
`(tenant_id, resident_id, version)`, and
`(tenant_id, resident_id, calibration_version)`.

- [x] **Step 4: Add Alembic revision `0002_status_calibration`**

Create the same schema and indexes in migration form. Its downgrade drops only
the three Checkpoint A tables in child-first order.

- [x] **Step 5: Run schema, downgrade, and full migration tests**

Run:

```bash
python3 -m pytest -q tests/persistence/test_migrations.py tests/persistence/test_status_schema.py
python3 -m pytest -q tests/persistence/test_session.py
```

Expected: all pass on migrated SQLite with foreign keys enabled.

- [x] **Step 6: Commit Task 2**

```bash
git add backend/app/db/models.py backend/app/db/migrations tests/persistence
git commit -m "feat: persist monitoring and calibration history"
```

---

### Task 3: Implement Tenant-Scoped Status Repositories

**Files:**
- Create: `backend/app/db/status_mappers.py`
- Create: `backend/app/db/status_repositories.py`
- Test: `tests/persistence/test_status_repositories.py`

**Interfaces:**
- Consumes: Task 2 rows plus `MonitoringSnapshot`, `CalibrationProgress`, and `SetupChangeAction`.
- Produces: `StoredMonitoringStatus`, `StoredCalibration`, `MonitoringStatusRepository`, and `CalibrationRepository` used by Tasks 4–6.

- [x] **Step 1: Write failing round-trip and stale-version tests**

Cover active, away, limited, and unavailable monitoring snapshots; dimension
progress; ordered setup history; UTC normalization; missing/cross-tenant
lookups; append-only history; and stale expected versions.

```python
def test_calibration_repository_rejects_stale_expected_version(session):
    stored = repository.current("tenant_demo", "resident_demo_a")
    repository.save("tenant_demo", changed, expected_version=stored.version)
    with pytest.raises(ConcurrentUpdateError):
        repository.save("tenant_demo", changed_again, expected_version=stored.version)
```

- [x] **Step 2: Run repository tests and verify RED**

Run: `python3 -m pytest -q tests/persistence/test_status_repositories.py`

Expected: imports fail because the focused repository module does not exist.

- [x] **Step 3: Implement immutable stored wrappers and mappers**

```python
@dataclass(frozen=True)
class StoredMonitoringStatus:
    resident_id: str
    room_id: str
    observed_at: datetime
    snapshot: MonitoringSnapshot


@dataclass(frozen=True)
class StoredCalibration:
    resident_id: str
    version: int
    recorded_at: datetime
    progress: CalibrationProgress
```

Map enum values explicitly. Normalize database timestamps to `timezone.utc`.
Reject malformed stored JSON rather than silently dropping reasons or
dimensions.

- [x] **Step 4: Implement repository reads and writes**

`MonitoringStatusRepository` exposes:

```python
record(tenant_id: str, stored: StoredMonitoringStatus) -> None
latest(tenant_id: str, resident_id: str) -> StoredMonitoringStatus
timeline(tenant_id: str, resident_id: str) -> list[StoredMonitoringStatus]
```

`CalibrationRepository` exposes:

```python
current(tenant_id: str, resident_id: str) -> StoredCalibration
save(
    tenant_id: str,
    stored: StoredCalibration,
    expected_version: int,
) -> StoredCalibration
```

`save` inserts version `expected_version + 1`, stores only the newest setup
action for that version, flushes, then rehydrates the full ordered history.
Convert uniqueness collisions to `ConcurrentUpdateError`.

- [x] **Step 5: Run focused and regression repository suites**

Run:

```bash
python3 -m pytest -q tests/persistence/test_status_repositories.py
python3 -m pytest -q tests/persistence/test_repositories.py
```

Expected: all pass.

- [x] **Step 6: Commit Task 3**

```bash
git add backend/app/db/status_mappers.py backend/app/db/status_repositories.py tests/persistence/test_status_repositories.py
git commit -m "feat: add tenant-scoped status repositories"
```

---

### Task 4: Expose Resident Status, Awareness, and Calibration Reads

**Files:**
- Create: `backend/app/services/status_queries.py`
- Create: `backend/app/api/v1/resident_status.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `tests/api/test_status_read_api.py`

**Interfaces:**
- Consumes: Task 1 response models and Task 3 repositories.
- Produces: three tenant-scoped GET routes used by the acceptance story and Rishit's clinic client.

- [x] **Step 1: Write failing API story tests**

Prove exact response bodies, chronological awareness ordering, nested schema
versions, current calibration composition, OpenAPI response references,
method-not-allowed envelopes, missing resources, and cross-tenant
indistinguishability.

```python
def test_away_is_timeline_awareness_not_an_event(api_client):
    timeline = api_client.get(
        "/v1/residents/resident_demo_a/awareness",
        headers=ACCESS_HEADERS,
    ).json()
    assert any(item["presence_state"] == "resident_away" for item in timeline["items"])
    events = api_client.get(
        "/v1/residents/resident_demo_a/events",
        headers=ACCESS_HEADERS,
    ).json()
    assert all(item["objective_family"] != "resident_away" for item in events["items"])
```

- [x] **Step 2: Run API tests and verify RED**

Run: `python3 -m pytest -q tests/api/test_status_read_api.py`

Expected: the three routes return 404.

- [x] **Step 3: Implement response mapping service**

`ProductStatusQueryService` checks the resident assignment first, then maps
the latest status/calibration or ordered timeline into Task 1 contracts. It
does not expose rows or synthesize measurements.

- [x] **Step 4: Add dependency provider and router**

Register:

```python
@router.get("/{resident_id}/status", response_model=ResidentStatusResponse)
@router.get("/{resident_id}/awareness", response_model=AwarenessTimelineResponse)
@router.get("/{resident_id}/calibration", response_model=CalibrationResponse)
```

Reuse `access_context`, `database_session`, and the standard read-error
responses.

- [x] **Step 5: Run API/OpenAPI/full read suites**

Run:

```bash
python3 -m pytest -q tests/api/test_status_read_api.py tests/api/test_read_api.py tests/api/test_contracts.py
```

Expected: all pass.

- [x] **Step 6: Commit Task 4**

```bash
git add backend/app/services/status_queries.py backend/app/api tests/api/test_status_read_api.py
git commit -m "feat: expose resident status and awareness reads"
```

---

### Task 5: Add Atomic Setup-Change Recalibration

**Files:**
- Create: `backend/app/services/setup_commands.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/api/v1/resident_status.py`
- Test: `tests/api/test_setup_change_api.py`
- Test: `tests/persistence/test_setup_change_rollback.py`

**Interfaces:**
- Consumes: `SetupChangeRequest`, `CalibrationRepository`, `start_recalibration`, `IdempotencyService`, and `AuditLogRow`.
- Produces: idempotent `POST /v1/residents/{resident_id}/setup-changes` returning `CalibrationResponse`.

- [x] **Step 1: Write failing lifecycle and rollback tests**

Tests cover selective dimension reset, generated next setup version,
preserved unaffected dimensions/history/memory, replay, key conflict, stale
expected version, malformed dimension/reason/time, cross-tenant behavior,
audit record, database failure rollback, and restart durability.

```python
def test_setup_change_resets_only_selected_dimension(api_client):
    response = api_client.post(
        "/v1/residents/resident_demo_a/setup-changes",
        headers={**ACCESS_HEADERS, "Idempotency-Key": "move-1"},
        json={
            "schema_version": "1.0",
            "reason": "device_moved",
            "affected_dimensions": ["movement"],
            "changed_at": "2026-08-24T22:00:00Z",
            "expected_calibration_version": 1,
        },
    )
    assert response.status_code == 200
    dimensions = {item["dimension"]: item for item in response.json()["dimensions"]}
    assert dimensions["movement"]["status"] == "calibrating"
    assert dimensions["respiratory_rate"]["status"] == "established"
```

- [x] **Step 2: Run setup tests and verify RED**

Run: `python3 -m pytest -q tests/api/test_setup_change_api.py tests/persistence/test_setup_change_rollback.py`

Expected: POST route is absent.

- [x] **Step 3: Implement command service**

`SetupChangeCommandService.change_setup(...)`:

1. verifies resident ownership;
2. loads current calibration;
3. checks `expected_calibration_version`;
4. generates `setup_<room_id>_v<next-version>`;
5. calls `start_recalibration` with actor/time/reason/dimensions;
6. saves the new calibration version;
7. appends `monitoring_setup.changed` audit details;
8. returns the stored calibration.

- [x] **Step 4: Execute through idempotency in the route**

Follow the existing event mutation pattern: reserve key, execute command,
store exact response body, commit once, rollback any exception, and return the
stored response on replay.

- [x] **Step 5: Run mutation, rollback, concurrency, and regression suites**

Run:

```bash
python3 -m pytest -q tests/api/test_setup_change_api.py tests/persistence/test_setup_change_rollback.py
python3 -m pytest -q tests/api/test_event_lifecycle_api.py tests/persistence/test_optimistic_concurrency.py
```

Expected: all pass.

- [x] **Step 6: Commit Task 5**

```bash
git add backend/app/services/setup_commands.py backend/app/api tests/api/test_setup_change_api.py tests/persistence/test_setup_change_rollback.py
git commit -m "feat: add durable selective recalibration action"
```

---

### Task 6: Seed and Prove the Complete Checkpoint A Story

**Files:**
- Modify: `backend/app/db/seed.py`
- Create: `backend/app/checkpoints/__init__.py`
- Create: `backend/app/checkpoints/status_calibration.py`
- Create: `tests/api/test_status_calibration_story.py`
- Modify: `tests/persistence/test_restart_durability.py`
- Modify: `docs/CURRENT_STAGE.md`
- Create: `docs/PHASE_2_CHECKPOINT_A_REVIEW.md`

**Interfaces:**
- Consumes: all Checkpoint A API paths and existing event/memory paths.
- Produces: deterministic synthetic seed history and `python3 -m backend.app.checkpoints.status_calibration` founder verification command.

- [x] **Step 1: Write the failing end-to-end restart story**

The story must prove, through the real API:

1. resident begins active;
2. resident-away appears in awareness but creates no warning event;
3. return resumes active monitoring;
4. possible multi-person presence is limited and excludes learning;
5. current calibration is established before setup change;
6. a device-moved action resets only movement;
7. status, awareness, setup history, and calibration survive app restart;
8. replay does not create another calibration/audit/idempotency effect.

- [x] **Step 2: Run story and verify RED**

Run: `python3 -m pytest -q tests/api/test_status_calibration_story.py`

Expected: seed data and checkpoint module are missing.

- [x] **Step 3: Extend deterministic synthetic seed**

Seed ordered monitoring snapshots and calibration version 1 for
`resident_demo_a`. Values remain synthetic and use existing domain functions
to derive monitoring decisions rather than hand-writing contradictory states.

- [x] **Step 4: Add the founder checkpoint command**

The module creates a temporary migrated database, seeds it, calls the real API,
performs the setup change, restarts the application, and prints:

```text
PASS resident active monitoring is available
PASS resident away is awareness, not a warning
PASS resident return resumes monitoring
PASS possible multi-person state limits learning
PASS setup change recalibrates only movement
PASS status and calibration survive restart
CHECKPOINT A READY
```

Any mismatch exits nonzero with one plain-language `FAIL` line.

- [x] **Step 5: Update status and review documentation**

Record Checkpoint A as complete only after all commands pass. State that device
health, preferences/memory administration, and the full clinic handoff remain
open Checkpoints B–D.

- [x] **Step 6: Run the complete verification gate**

Run:

```bash
python3 -m backend.app.checkpoints.status_calibration
python3 -m pytest -q
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q backend tests
git diff --check
```

Expected: checkpoint prints all PASS lines; every automated suite passes.

- [x] **Step 7: Refresh graph and commit Task 6**

Run: `graphify update .`

```bash
git add backend tests docs graphify-out
git commit -m "feat: complete phase 2 resident status checkpoint"
```

---

### Task 7: Review, Fix, Merge, and Continue

**Files:**
- Review all files changed since `main`.
- Update only files required by actionable findings.

**Interfaces:**
- Consumes: completed Checkpoint A branch and verification evidence.
- Produces: merged, reviewed Checkpoint A and clean `main` for Checkpoint B.

- [ ] **Step 1: Review scope and contract compliance**

Check every spec requirement, tenant boundary, transaction, error path,
synthetic-policy label, and frontend response against the final diff.

- [ ] **Step 2: Run Greploop**

Run the repository Greptile workflow for up to five iterations. Fix valid
findings test-first, resolve addressed threads, and require 5/5 confidence with
zero unresolved actionable comments.

- [ ] **Step 3: Push and open the scoped pull request**

Use a product-level title and body describing what caregivers can now see,
what survives restart, how Akshar can test it, and what remains Checkpoint B.

- [ ] **Step 4: Wait for required checks and squash merge**

Require `repository-policy` and Greptile success. Squash merge and delete the
source branch according to repository policy.

- [ ] **Step 5: Verify merged `main`**

Run the founder checkpoint command and full pytest suite from updated `main`.
Only then mark Checkpoint A complete in the working plan and start the
Checkpoint B design/plan/build loop.
