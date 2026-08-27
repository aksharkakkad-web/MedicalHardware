# Phase 2 Product Backbone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist one complete caregiver event journey behind a versioned Product API and prove that its assignment, history, feedback, and resident memory survive an application restart.

**Architecture:** Keep `backend/app/domain/` as the product-rules core. FastAPI routes translate versioned Pydantic contracts into application-service commands; services own transaction and tenant boundaries; SQLAlchemy repositories map durable rows to the existing immutable domain objects. A database URL selects deterministic SQLite for local tests or Postgres/Supabase for shared environments without changing service or API behavior.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3, SQLite for local tests, Postgres/Supabase-compatible production schema, pytest/httpx.

**Spec:** `docs/superpowers/specs/2026-08-27-phase2-product-backbone-design.md`

## Global Constraints

- Reuse the existing monitoring, calibration, event, feedback, and resident-memory rules; do not create a parallel rules engine.
- V1 has one assigned resident per monitored room and no RFID identity layer.
- All public API objects and error envelopes carry `schema_version="1.0"`.
- Store only synthetic identifiers and labels; never add real PHI to fixtures, logs, or tests.
- Use timezone-aware UTC datetimes everywhere.
- Mutating requests require `Idempotency-Key`, `X-Tenant-Id`, and `X-Actor-Id`.
- A cross-tenant lookup returns not found and never reveals that the record exists.
- One command is one transaction; event state, histories, feedback, memory, idempotency, and audit effects commit or roll back together.
- Resolved events remain immutable; later recurrences are separate linked events.
- Keep the existing 72 Phase 1 tests green throughout.
- No sensor ingestion, fusion, anomaly intelligence, AI, notification delivery, real authentication provider, deployment, or clinical threshold work belongs in this slice.

---

### Task 1: Backend Runtime and Health Boundary

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_health.py`
- Modify: `docs/PHASE_GATES.md`

**Interfaces:**
- Consumes: Python 3.12+ and the repository's existing `backend` package.
- Produces: `backend.app.main.create_app(settings: Settings | None = None) -> FastAPI`, `backend.app.config.Settings`, and `GET /health` returning a versioned health object.

- [ ] **Step 1: Mark Phase 2 in progress**

Update the current-status table in `docs/PHASE_GATES.md` so Phase 2 reads `In progress`, while Phase 1 remains `Complete`. Do not change the Phase 2 scope or exit checkpoint.

- [ ] **Step 2: Write the failing health-contract test**

```python
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_is_versioned_and_reports_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "status": "ready",
        "service": "product-api",
    }
```

- [ ] **Step 3: Run the health test to verify RED**

Run: `python3 -m pytest tests/api/test_health.py -q`

Expected: FAIL because `backend.app.main` does not exist.

- [ ] **Step 4: Define the installable runtime**

Create `pyproject.toml` with these exact dependency ranges and test settings:

```toml
[build-system]
requires = ["setuptools>=75"]
build-backend = "setuptools.build_meta"

[project]
name = "contactless-monitoring-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.16,<2",
  "fastapi>=0.116,<1",
  "pydantic-settings>=2.10,<3",
  "psycopg[binary]>=3.2,<4",
  "sqlalchemy>=2.0,<3",
  "uvicorn[standard]>=0.35,<1",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.28,<1",
  "pytest>=8.4,<9",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `.env.example`:

```dotenv
APP_ENV=development
DATABASE_URL=sqlite+pysqlite:///./local-product.db
```

- [ ] **Step 5: Implement settings and the health application**

```python
# backend/app/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "test"
    database_url: str = "sqlite+pysqlite:///:memory:"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# backend/app/main.py
from fastapi import FastAPI

from backend.app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Contactless Monitoring Product API", version="0.1.0")
    app.state.settings = settings or Settings()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "schema_version": "1.0",
            "status": "ready",
            "service": "product-api",
        }

    return app


app = create_app()
```

- [ ] **Step 6: Install and verify GREEN**

Run: `python3 -m pip install -e '.[dev]'`

Run: `python3 -m pytest tests/api/test_health.py -q`

Expected: 1 passed.

- [ ] **Step 7: Run the full existing suite**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`

Expected: 72 tests pass.

- [ ] **Step 8: Commit the runtime boundary**

```bash
git add pyproject.toml .env.example backend/app/config.py backend/app/main.py tests/api docs/PHASE_GATES.md
git commit -m "feat: start phase 2 product API runtime"
```

---

### Task 2: Durable Schema and Migration Gate

**Files:**
- Create: `alembic.ini`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Create: `backend/app/db/models.py`
- Create: `backend/app/db/migrations/env.py`
- Create: `backend/app/db/migrations/script.py.mako`
- Create: `backend/app/db/migrations/versions/0001_product_backbone.py`
- Create: `tests/persistence/__init__.py`
- Create: `tests/persistence/test_migrations.py`

**Interfaces:**
- Consumes: `Settings.database_url` from Task 1.
- Produces: `Base`, `create_engine_for_url(database_url: str) -> Engine`, `create_session_factory(engine: Engine) -> sessionmaker[Session]`, and the initial durable tables.

- [ ] **Step 1: Write the failing migration test**

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


EXPECTED_TABLES = {
    "tenants",
    "rooms",
    "residents",
    "room_resident_assignments",
    "monitoring_events",
    "event_actions",
    "event_priority_history",
    "feedback_records",
    "resident_memory_snapshots",
    "resident_memory_entries",
    "idempotency_records",
    "audit_log",
}


def test_initial_migration_creates_product_backbone(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert EXPECTED_TABLES <= tables
```

- [ ] **Step 2: Run the migration test to verify RED**

Run: `python3 -m pytest tests/persistence/test_migrations.py -q`

Expected: FAIL because `alembic.ini` and the migration do not exist.

- [ ] **Step 3: Create engine/session helpers**

```python
# backend/app/db/base.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

```python
# backend/app/db/session.py
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_for_url(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
```

- [ ] **Step 4: Define the initial SQLAlchemy rows**

Create `backend/app/db/models.py` with typed SQLAlchemy 2 declarations. Use string IDs, timezone-aware datetime columns, JSON only for immutable ID arrays, child tables for action/priority/memory history, and integer optimistic versions.

The exact required row interfaces are:

```python
class TenantRow(Base):
    __tablename__ = "tenants"
    tenant_id: Mapped[str]


class RoomRow(Base):
    __tablename__ = "rooms"
    room_id: Mapped[str]
    tenant_id: Mapped[str]
    label: Mapped[str]


class ResidentRow(Base):
    __tablename__ = "residents"
    resident_id: Mapped[str]
    tenant_id: Mapped[str]
    display_label: Mapped[str]


class RoomResidentAssignmentRow(Base):
    __tablename__ = "room_resident_assignments"
    assignment_id: Mapped[str]
    tenant_id: Mapped[str]
    room_id: Mapped[str]
    resident_id: Mapped[str]
    status: Mapped[str]
    effective_from: Mapped[datetime]
    effective_to: Mapped[datetime | None]


class MonitoringEventRow(Base):
    __tablename__ = "monitoring_events"
    event_id: Mapped[str]
    tenant_id: Mapped[str]
    episode_id: Mapped[str]
    resident_id: Mapped[str]
    room_id: Mapped[str]
    objective_family: Mapped[str]
    headline: Mapped[str]
    priority: Mapped[str]
    status: Mapped[str]
    created_at: Mapped[datetime]
    last_signal_at: Mapped[datetime]
    signal_count: Mapped[int]
    related_event_ids: Mapped[list[str]]
    recurrence_count: Mapped[int]
    overdue_at: Mapped[datetime | None]
    resolution_outcome: Mapped[str | None]
    episode_policy_version: Mapped[str]
    episode_policy_test_only: Mapped[bool]
    resident_memory_version: Mapped[int | None]
    resident_memory_entry_ids: Mapped[list[str]]
    version: Mapped[int]


class EventActionRow(Base):
    __tablename__ = "event_actions"
    action_id: Mapped[int]
    tenant_id: Mapped[str]
    event_id: Mapped[str]
    sequence: Mapped[int]
    action: Mapped[str]
    actor_id: Mapped[str]
    occurred_at: Mapped[datetime]
    previous_status: Mapped[str]
    status: Mapped[str]
    resolution_outcome: Mapped[str | None]


class EventPriorityHistoryRow(Base):
    __tablename__ = "event_priority_history"
    priority_history_id: Mapped[int]
    tenant_id: Mapped[str]
    event_id: Mapped[str]
    sequence: Mapped[int]
    previous_priority: Mapped[str | None]
    priority: Mapped[str]
    actor_id: Mapped[str]
    changed_at: Mapped[datetime]


class FeedbackRecordRow(Base):
    __tablename__ = "feedback_records"
    feedback_id: Mapped[str]
    tenant_id: Mapped[str]
    event_id: Mapped[str]
    resident_id: Mapped[str]
    actor_id: Mapped[str]
    outcome: Mapped[str]
    actual_event_label: Mapped[str]
    routine: Mapped[bool]
    created_at: Mapped[datetime]
    memory_updated: Mapped[bool]
    baseline_window_eligible: Mapped[bool]
    global_label_recorded: Mapped[bool]


class ResidentMemorySnapshotRow(Base):
    __tablename__ = "resident_memory_snapshots"
    memory_snapshot_id: Mapped[int]
    tenant_id: Mapped[str]
    resident_id: Mapped[str]
    version: Mapped[int]
    created_at: Mapped[datetime]


class ResidentMemoryEntryRow(Base):
    __tablename__ = "resident_memory_entries"
    memory_entry_row_id: Mapped[int]
    entry_id: Mapped[str]
    tenant_id: Mapped[str]
    resident_id: Mapped[str]
    memory_version: Mapped[int]
    description: Mapped[str]
    source_feedback_id: Mapped[str]
    status: Mapped[str]
    created_by: Mapped[str]
    created_at: Mapped[datetime]
    retired_by: Mapped[str | None]
    retired_at: Mapped[datetime | None]
    retirement_reason: Mapped[str | None]


class IdempotencyRecordRow(Base):
    __tablename__ = "idempotency_records"
    idempotency_id: Mapped[int]
    tenant_id: Mapped[str]
    actor_id: Mapped[str]
    key: Mapped[str]
    request_fingerprint: Mapped[str]
    response_status: Mapped[int]
    response_body: Mapped[dict[str, object]]
    created_at: Mapped[datetime]


class AuditLogRow(Base):
    __tablename__ = "audit_log"
    audit_id: Mapped[int]
    tenant_id: Mapped[str]
    actor_id: Mapped[str]
    action: Mapped[str]
    target_type: Mapped[str]
    target_id: Mapped[str]
    occurred_at: Mapped[datetime]
    details: Mapped[dict[str, object]]
```

Apply primary keys, foreign keys, uniqueness on `(tenant_id, actor_id, key)`, `(tenant_id, event_id)` for feedback, `(event_id, sequence)`, `(resident_id, version)`, `(tenant_id, resident_id, memory_version, entry_id)`, and `(tenant_id, room_id, status)` for the synthetic active-assignment path. Add indexes on tenant/resident/event foreign-key lookup columns.

- [ ] **Step 5: Configure Alembic and create the explicit initial migration**

Set `target_metadata = Base.metadata` in `backend/app/db/migrations/env.py`. Import `backend.app.db.models` before assigning metadata so all tables register. Create revision `0001_product_backbone` with `upgrade()` creating exactly the twelve tables above and `downgrade()` dropping them in reverse foreign-key order.

- [ ] **Step 6: Run migration and model checks**

Run: `python3 -m pytest tests/persistence/test_migrations.py -q`

Expected: 1 passed.

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`

Expected: 72 Phase 1 tests plus the migration test pass under pytest; the unittest command remains 72/72.

- [ ] **Step 7: Commit the schema**

```bash
git add alembic.ini backend/app/db tests/persistence
git commit -m "feat: add durable phase 2 product schema"
```

---

### Task 3: Domain Hydration, Repositories, and Synthetic Seed

**Files:**
- Modify: `backend/app/domain/events.py`
- Modify: `backend/app/domain/feedback.py`
- Create: `backend/app/db/mappers.py`
- Create: `backend/app/db/repositories.py`
- Create: `backend/app/db/seed.py`
- Create: `tests/persistence/test_repositories.py`
- Create: `tests/persistence/test_seed.py`

**Interfaces:**
- Consumes: SQLAlchemy rows/session factory from Task 2 and immutable domain records from Phase 1.
- Produces: domain hydration entry points; `ResidentRepository`, `EventRepository`, `FeedbackRepository`; `seed_synthetic_story(session: Session) -> SeededStory`.

- [ ] **Step 1: Write failing hydration and round-trip tests**

```python
def test_event_round_trip_preserves_full_history(session) -> None:
    story = seed_synthetic_story(session)
    loaded = EventRepository(session).get(story.tenant_id, story.event_id)

    assert loaded.event.event_id == story.event_id
    assert [action.action.value for action in loaded.event.action_history] == ["opened"]
    assert loaded.event.priority_history[0].priority.value == "high"
    assert loaded.version == 1


def test_cross_tenant_repository_lookup_returns_none(session) -> None:
    story = seed_synthetic_story(session)
    assert EventRepository(session).find("tenant_other", story.event_id) is None
```

- [ ] **Step 2: Run repository tests to verify RED**

Run: `python3 -m pytest tests/persistence/test_repositories.py tests/persistence/test_seed.py -q`

Expected: FAIL because repositories and seed modules do not exist.

- [ ] **Step 3: Add explicit domain hydration**

Change `EventStore.__init__` without breaking existing callers:

```python
def __init__(
    self,
    quiet_gap: timedelta | None = None,
    *,
    policy: SyntheticEventEpisodePolicy | None = None,
    initial_events: Sequence[MonitoringEvent] = (),
) -> None:
    # preserve current policy validation
    self._events = {event.event_id: event for event in initial_events}
    if len(self._events) != len(initial_events):
        raise ValueError("initial_events must have unique event IDs")
```

Change `FeedbackService.__init__` without breaking existing callers:

```python
def __init__(
    self,
    *,
    initial_memories: Sequence[ResidentMemory] = (),
    initial_decisions: Sequence[LearningDecision] = (),
) -> None:
    self._memories = {memory.resident_id: memory for memory in initial_memories}
    self._feedback = {
        decision.feedback.feedback_id: decision.feedback
        for decision in initial_decisions
    }
    self._decisions_by_event_id = {
        decision.feedback.event_id: decision
        for decision in initial_decisions
    }
```

Add regression tests to the existing event and feedback test modules proving hydrated transitions/retries preserve current behavior.

- [ ] **Step 4: Implement exact mapping functions**

Create public functions `event_to_rows(tenant_id, event, version) -> EventRowBundle`, `event_from_rows(event_row, action_rows, priority_rows) -> StoredEvent`, `memory_to_rows(tenant_id, memory, created_at) -> MemoryRowBundle`, `memory_from_rows(snapshot_row, entry_rows) -> ResidentMemory`, `feedback_to_row(tenant_id, decision) -> FeedbackRecordRow`, and `feedback_from_row(row, memory) -> LearningDecision`.

`event_to_rows` copies every scalar event field, stores enum `.value`, enumerates action/priority tuples from sequence 1, and converts tuple ID fields to JSON lists. `event_from_rows` sorts child rows by sequence, reconstructs enums, converts ID lists back to tuples, and returns `StoredEvent(event, version)`. Memory mapping writes one immutable snapshot plus the complete entries for that version. Feedback mapping persists and reconstructs all three learning-effect booleans.

Define frozen `EventRowBundle`, `MemoryRowBundle`, and `StoredEvent` dataclasses in the same module. Enum values store as strings and reconstruct through the existing enums. SQLite-returned naive datetimes must be normalized to timezone-aware UTC at this mapper boundary.

- [ ] **Step 5: Implement tenant-scoped repositories**

Create `ResidentRepository.list(tenant_id) -> list[ResidentRecord]` and `find(tenant_id, resident_id) -> ResidentRecord | None`; both join the active assignment and room while filtering every joined row by tenant.

Create `EventRepository.list_for_resident(tenant_id, resident_id) -> list[StoredEvent]`, `find(tenant_id, event_id) -> StoredEvent | None`, `get(tenant_id, event_id) -> StoredEvent`, and `save(tenant_id, event, expected_version) -> StoredEvent`. Reads query the event plus ordered child histories and call `event_from_rows`; `get` raises tenant-safe `NotFoundError` when `find` returns none.

Create `FeedbackRepository.find_by_event(tenant_id, event_id) -> LearningDecision | None`, `current_memory(tenant_id, resident_id) -> ResidentMemory`, and `save_decision(tenant_id, decision) -> None`. Current memory selects the greatest snapshot version for the tenant/resident, then loads entries for exactly that version; no snapshot returns `ResidentMemory(resident_id, 0, ())`.

`EventRepository.save` must issue an update constrained by `event_id`, `tenant_id`, and `version == expected_version`, then insert only new action/priority rows and increment the version. Zero updated rows raises `ConcurrentUpdateError`.

- [ ] **Step 6: Implement deterministic synthetic seeding**

Define `SeededStory` with IDs and use stable values:

```python
TENANT_ID = "tenant_demo"
ROOM_ID = "room_214"
RESIDENT_ID = "resident_demo_a"
EVENT_ID = "evt_phase2_demo"


@dataclass(frozen=True)
class SeededStory:
    tenant_id: str
    room_id: str
    resident_id: str
    event_id: str


def seed_synthetic_story(session: Session) -> SeededStory:
    # insert only when TENANT_ID is absent; commit one open HIGH event
    # opened at 2026-08-24T21:02:11Z with one action and priority entry
    return SeededStory(TENANT_ID, ROOM_ID, RESIDENT_ID, EVENT_ID)
```

Running `python3 -m backend.app.db.seed` uses `Settings.database_url`, upgrades migrations to head, seeds once, and prints only the four synthetic IDs without credentials or database contents.

- [ ] **Step 7: Verify repositories and the Phase 1 suite**

Run: `python3 -m pytest tests/persistence/test_repositories.py tests/persistence/test_seed.py tests/event_domain tests/feedback_domain -q`

Expected: all pass.

- [ ] **Step 8: Commit the persistence adapters**

```bash
git add backend/app/domain backend/app/db tests/persistence tests/event_domain tests/feedback_domain
git commit -m "feat: persist phase 1 event and memory state"
```

---

### Task 4: Versioned Product Contracts and Read API

**Files:**
- Create: `backend/app/contracts/__init__.py`
- Create: `backend/app/contracts/common.py`
- Create: `backend/app/contracts/residents.py`
- Create: `backend/app/contracts/events.py`
- Create: `backend/app/contracts/feedback.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/errors.py`
- Create: `backend/app/services/queries.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/api/errors.py`
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/router.py`
- Create: `backend/app/api/v1/residents.py`
- Create: `backend/app/api/v1/events.py`
- Modify: `backend/app/main.py`
- Create: `tests/conftest.py`
- Create: `tests/api/test_read_api.py`

**Interfaces:**
- Consumes: repositories from Task 3.
- Produces: versioned response/error contracts and the six read/health paths in the approved design.

- [ ] **Step 1: Write failing read-API contract tests**

```python
def test_list_residents_is_tenant_scoped(api_client) -> None:
    response = api_client.get(
        "/v1/residents",
        headers={"X-Tenant-Id": "tenant_demo", "X-Actor-Id": "operator_1"},
    )
    assert response.status_code == 200
    assert response.json()["items"][0] == {
        "schema_version": "1.0",
        "resident_id": "resident_demo_a",
        "display_label": "Resident A",
        "room_id": "room_214",
        "room_label": "Room 214",
        "assignment_status": "active",
    }


def test_cross_tenant_event_is_not_found(api_client) -> None:
    response = api_client.get(
        "/v1/events/evt_phase2_demo",
        headers={"X-Tenant-Id": "tenant_other", "X-Actor-Id": "operator_1"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
```

- [ ] **Step 2: Run the read tests to verify RED**

Run: `python3 -m pytest tests/api/test_read_api.py -q`

Expected: FAIL because `/v1` routes do not exist.

- [ ] **Step 3: Define shared contracts and error types**

```python
# backend/app/contracts/common.py
from typing import Literal
from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class ErrorDetail(ContractModel):
    code: str
    message: str
    field: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
```

Define service errors `ProductError`, `NotFoundError`, `InvalidTransitionError`, `IdempotencyConflictError`, and `ConcurrentUpdateError`, each with stable `code`, `message`, and HTTP mapping performed only in `backend/app/api/errors.py`.

- [ ] **Step 4: Define resident and event response contracts**

Create strict Pydantic response models matching these fields:

```python
class ResidentSummary(ContractModel):
    resident_id: str
    display_label: str
    room_id: str
    room_label: str
    assignment_status: Literal["active"]


class ResidentListResponse(ContractModel):
    items: list[ResidentSummary]


class EventActionResponse(ContractModel):
    action: EventActionType
    actor_id: str
    occurred_at: datetime
    previous_status: EventStatus
    status: EventStatus
    resolution_outcome: ResolutionOutcome | None


class EventPriorityHistoryResponse(ContractModel):
    previous_priority: EventPriority | None
    priority: EventPriority
    actor_id: str
    changed_at: datetime


class EventResponse(ContractModel):
    event_id: str
    episode_id: str
    resident_id: str
    room_id: str
    objective_family: str
    headline: str
    priority: EventPriority
    status: EventStatus
    created_at: datetime
    last_signal_at: datetime
    signal_count: int
    related_event_ids: list[str]
    recurrence_count: int
    overdue_at: datetime | None
    overdue: bool
    resolution_outcome: ResolutionOutcome | None
    action_history: list[EventActionResponse]
    priority_history: list[EventPriorityHistoryResponse]
    resident_memory_version: int | None
    resident_memory_entry_ids: list[str]
    version: int


class EventListResponse(ContractModel):
    items: list[EventResponse]
```

- [ ] **Step 5: Implement tenant/actor dependencies and query services**

```python
@dataclass(frozen=True)
class AccessContext:
    tenant_id: str
    actor_id: str


def access_context(
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-Id")],
    x_actor_id: Annotated[str, Header(alias="X-Actor-Id")],
) -> AccessContext:
    return AccessContext(
        require_nonblank_text(x_tenant_id, "X-Tenant-Id"),
        require_nonblank_text(x_actor_id, "X-Actor-Id"),
    )
```

`ProductQueryService` exposes `list_residents`, `get_resident`, `list_resident_events`, `get_event`, and `get_resident_memory`, always requiring an `AccessContext`.

- [ ] **Step 6: Wire the read routes**

Register `/v1` in `create_app`. Each request opens one session through a dependency, constructs the query service, returns a response contract, and closes the session. Register one exception handler that converts only known `ProductError` instances into `ErrorEnvelope`; unexpected errors remain generic 500 responses.

- [ ] **Step 7: Verify read contracts and OpenAPI**

Run: `python3 -m pytest tests/api/test_read_api.py tests/api/test_health.py -q`

Expected: all pass, including assertions that every 200 and documented error response includes schema version 1.0.

- [ ] **Step 8: Commit read APIs**

```bash
git add backend/app/contracts backend/app/services backend/app/api backend/app/main.py tests/api tests/conftest.py
git commit -m "feat: expose tenant-scoped phase 2 read APIs"
```

---

### Task 5: Caregiver Lifecycle Commands and Idempotency

**Files:**
- Create: `backend/app/services/idempotency.py`
- Create: `backend/app/services/event_commands.py`
- Modify: `backend/app/contracts/events.py`
- Modify: `backend/app/api/dependencies.py`
- Modify: `backend/app/api/v1/events.py`
- Create: `tests/api/test_event_lifecycle_api.py`
- Create: `tests/persistence/test_optimistic_concurrency.py`

**Interfaces:**
- Consumes: hydrated `EventStore`, `EventRepository`, access context, and API contracts.
- Produces: acknowledge/check/resolve commands with request idempotency, audit rows, chronology validation, and optimistic concurrency.

- [ ] **Step 1: Write failing lifecycle and retry tests**

```python
def test_complete_caregiver_lifecycle_is_auditable(api_client) -> None:
    headers = {
        "X-Tenant-Id": "tenant_demo",
        "X-Actor-Id": "operator_1",
        "Idempotency-Key": "ack-1",
    }
    acknowledged = api_client.post(
        "/v1/events/evt_phase2_demo/acknowledge",
        headers=headers,
        json={"occurred_at": "2026-08-24T21:03:00Z"},
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"


def test_same_idempotency_key_replays_original_response(api_client) -> None:
    headers = {
        "X-Tenant-Id": "tenant_demo",
        "X-Actor-Id": "operator_1",
        "Idempotency-Key": "ack-retry",
    }
    first = api_client.post(
        "/v1/events/evt_phase2_demo/acknowledge",
        headers=headers,
        json={"occurred_at": "2026-08-24T21:03:00Z"},
    )
    second = api_client.post(
        "/v1/events/evt_phase2_demo/acknowledge",
        headers=headers,
        json={"occurred_at": "2026-08-24T21:03:00Z"},
    )
    assert second.status_code == first.status_code
    assert second.json() == first.json()
```

- [ ] **Step 2: Run lifecycle tests to verify RED**

Run: `python3 -m pytest tests/api/test_event_lifecycle_api.py tests/persistence/test_optimistic_concurrency.py -q`

Expected: FAIL because command routes/services do not exist.

- [ ] **Step 3: Define strict action contracts**

```python
class EventActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occurred_at: AwareDatetime


class ResolveEventRequest(EventActionRequest):
    outcome: ResolutionOutcome
```

- [ ] **Step 4: Implement request fingerprinting and replay**

`IdempotencyService.execute` uses SHA-256 over canonical JSON containing tenant, actor, HTTP method, path, and validated request body:

```python
def fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
```

For `(tenant_id, actor_id, key)`: no record runs the command and stores status/body in the same transaction; same fingerprint returns stored status/body; different fingerprint raises `IdempotencyConflictError`.

- [ ] **Step 5: Implement event command service through the domain store**

Implement `EventCommandService.acknowledge(context, event_id, occurred_at) -> StoredEvent`, `check(context, event_id, occurred_at) -> StoredEvent`, and `resolve(context, event_id, occurred_at, outcome) -> StoredEvent`.

Each method loads the tenant-scoped event, hydrates `EventStore(initial_events=(stored.event,))`, invokes the existing domain transition, saves with `expected_version=stored.version`, and appends one `AuditLogRow`. Convert domain `ValueError` into `InvalidTransitionError` without changing the domain exception behavior used by Phase 1 tests.

- [ ] **Step 6: Wire action routes through one transaction**

Routes require access headers and `Idempotency-Key`. Call `IdempotencyService.execute` with a closure that invokes `EventCommandService`; commit only after the event, action history, audit row, and idempotency response are staged. Roll back on every exception.

- [ ] **Step 7: Prove optimistic concurrency**

Create two sessions that both load version 1. Save the first transition successfully. Attempt to save the second using expected version 1 and assert `ConcurrentUpdateError`; confirm only one new event action and one audit row exist.

- [ ] **Step 8: Run lifecycle, concurrency, and Phase 1 event tests**

Run: `python3 -m pytest tests/api/test_event_lifecycle_api.py tests/persistence/test_optimistic_concurrency.py tests/event_domain -q`

Expected: all pass.

- [ ] **Step 9: Commit lifecycle commands**

```bash
git add backend/app/services backend/app/contracts/events.py backend/app/api tests/api/test_event_lifecycle_api.py tests/persistence/test_optimistic_concurrency.py
git commit -m "feat: persist idempotent caregiver event actions"
```

---

### Task 6: Trusted Feedback and Resident-Memory Transaction

**Files:**
- Create: `backend/app/services/feedback_commands.py`
- Modify: `backend/app/contracts/feedback.py`
- Modify: `backend/app/api/v1/events.py`
- Create: `tests/api/test_feedback_api.py`
- Create: `tests/persistence/test_feedback_rollback.py`

**Interfaces:**
- Consumes: resolved durable event, current durable memory, existing `FeedbackService`, idempotency service, repositories.
- Produces: `POST /v1/events/{event_id}/feedback`, durable feedback/memory, versioned response, and atomic rollback behavior.

- [ ] **Step 1: Write failing feedback/memory tests**

```python
def test_feedback_updates_memory_once(api_client, resolved_event) -> None:
    headers = {
        "X-Tenant-Id": "tenant_demo",
        "X-Actor-Id": "operator_1",
        "Idempotency-Key": "feedback-1",
    }
    response = api_client.post(
        "/v1/events/evt_phase2_demo/feedback",
        headers=headers,
        json={
            "actual_event_label": "Assisted movement",
            "routine": True,
            "created_at": "2026-08-24T21:06:00Z",
        },
    )
    assert response.status_code == 200
    assert response.json()["memory"]["version"] == 1
    assert response.json()["memory_updated"] is True


def test_feedback_failure_rolls_back_every_effect(session, faulting_repository) -> None:
    context = AccessContext("tenant_demo", "operator_1")
    service = FeedbackCommandService(
        session,
        event_repository=EventRepository(session),
        feedback_repository=faulting_repository,
    )
    with pytest.raises(RuntimeError, match="synthetic persistence failure"):
        service.submit_feedback(
            context,
            "evt_phase2_demo",
            "assisted_movement",
            True,
            datetime(2026, 8, 24, 21, 6, tzinfo=timezone.utc),
        )
    session.rollback()
    assert session.scalar(select(func.count()).select_from(FeedbackRecordRow)) == 0
    assert session.scalar(select(func.count()).select_from(ResidentMemorySnapshotRow)) == 0
    assert session.scalar(select(func.count()).select_from(AuditLogRow)) == 0
```

Seed and resolve `evt_phase2_demo` before the rollback assertion. The injected feedback repository raises after adding a feedback row but before adding the memory snapshot; the service/session boundary must roll the transaction back.

- [ ] **Step 2: Run feedback tests to verify RED**

Run: `python3 -m pytest tests/api/test_feedback_api.py tests/persistence/test_feedback_rollback.py -q`

Expected: FAIL because the feedback command route/service does not exist.

- [ ] **Step 3: Define strict feedback response contracts**

```python
class SubmitFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actual_event_label: str
    routine: bool
    created_at: AwareDatetime


class MemoryEntryResponse(ContractModel):
    entry_id: str
    description: str
    source_feedback_id: str
    status: Literal["active", "retired"]
    created_by: str
    created_at: datetime
    retired_by: str | None
    retired_at: datetime | None
    retirement_reason: str | None


class ResidentMemoryResponse(ContractModel):
    resident_id: str
    version: int
    entries: list[MemoryEntryResponse]


class FeedbackResponse(ContractModel):
    feedback_id: str
    event_id: str
    resident_id: str
    actor_id: str
    outcome: ResolutionOutcome
    actual_event_label: str
    routine: bool
    created_at: datetime


class LearningDecisionResponse(ContractModel):
    feedback: FeedbackResponse
    memory: ResidentMemoryResponse
    memory_updated: bool
    baseline_window_eligible: bool
    global_label_recorded: bool
```

- [ ] **Step 4: Implement feedback command through hydrated domain state**

Implement `FeedbackCommandService.submit_feedback(context, event_id, actual_event_label, routine, created_at) -> LearningDecision`.

Load the tenant-scoped resolved event, current memory, and existing decision. Build `initial_memories=(memory,)` when its version is greater than zero, otherwise an empty tuple; build `initial_decisions=(existing_decision,)` when feedback exists, otherwise an empty tuple. Hydrate `FeedbackService` with those values, invoke `submit_feedback`, persist the new feedback and complete memory snapshot, append one audit row, and return the domain decision. A conflicting second feedback maps to `InvalidTransitionError`; an identical `Idempotency-Key` replay returns the original serialized response without rerunning learning.

- [ ] **Step 5: Wire the feedback route and atomic rollback**

Run the command inside the same transaction as its idempotency record. Do not commit inside repositories. Add a test-only injected repository factory in application state so the rollback test can raise between feedback and memory persistence; the session dependency must roll the full transaction back.

- [ ] **Step 6: Verify feedback, memory, retry, and rollback behavior**

Run: `python3 -m pytest tests/api/test_feedback_api.py tests/persistence/test_feedback_rollback.py tests/feedback_domain -q`

Expected: all pass.

- [ ] **Step 7: Commit the feedback transaction**

```bash
git add backend/app/services/feedback_commands.py backend/app/contracts/feedback.py backend/app/api/v1/events.py tests/api/test_feedback_api.py tests/persistence/test_feedback_rollback.py
git commit -m "feat: persist trusted feedback and resident memory"
```

---

### Task 7: Restart Proof, Full Product Walkthrough, and Handoff

**Files:**
- Create: `tests/api/test_product_backbone_story.py`
- Create: `tests/persistence/test_restart_durability.py`
- Modify: `docs/CURRENT_STAGE.md`
- Modify: `docs/PHASE_GATES.md`
- Modify: `docs/DATA_CONTRACT.md`
- Create: `docs/PHASE_2_REVIEW.md`

**Interfaces:**
- Consumes: complete runtime, migration, seed, repositories, contracts, read API, lifecycle commands, and feedback transaction.
- Produces: one restart-safe caregiver story, frozen first-slice API examples, and a plain-language Phase 2 checkpoint record.

- [ ] **Step 1: Write the failing restart walkthrough**

```python
def test_product_backbone_survives_restart(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'product.db'}"
    first_client = build_seeded_client(database_url)
    headers = {"X-Tenant-Id": "tenant_demo", "X-Actor-Id": "operator_1"}

    post_action(first_client, "acknowledge", "ack-final", "2026-08-24T21:03:00Z")
    post_action(first_client, "checked", "check-final", "2026-08-24T21:04:00Z")
    resolve_event(first_client, "resolve-final", "2026-08-24T21:05:00Z", "false_positive")
    submit_feedback(first_client, "feedback-final", "2026-08-24T21:06:00Z")

    second_client = build_client_without_seeding(database_url)
    event = second_client.get("/v1/events/evt_phase2_demo", headers=headers).json()
    memory = second_client.get("/v1/residents/resident_demo_a/memory", headers=headers).json()

    assert event["status"] == "resolved"
    assert [item["action"] for item in event["action_history"]] == [
        "opened",
        "acknowledged",
        "checked",
        "resolved",
    ]
    assert memory["version"] == 1
    assert memory["entries"][0]["description"] == "assisted_movement"
```

- [ ] **Step 2: Run the walkthrough to verify RED**

Run: `python3 -m pytest tests/api/test_product_backbone_story.py tests/persistence/test_restart_durability.py -q`

Expected: FAIL until restart-safe app/test helpers and all durable reads are wired.

- [ ] **Step 3: Complete restart-safe application wiring**

Make `create_app(settings)` create one engine and session factory stored on application state. Test helpers run Alembic to head before starting the app and seed only when requested. Dispose the first engine before constructing the second client so the test proves a real process-boundary equivalent rather than a reused in-memory session.

- [ ] **Step 4: Freeze first-slice contract examples**

Update `docs/DATA_CONTRACT.md` with a clearly labeled “Phase 2 first durable slice” subsection containing:

- the six implemented read paths and four caregiver action paths;
- required development headers and idempotency behavior;
- the exact `ResidentSummary`, `EventResponse`, `LearningDecisionResponse`, and error envelope fields from Tasks 4–6;
- an explicit statement that evidence, trends, device health, interpretation, production authentication, and home real-data views are still deferred.

Do not modify telemetry, anomaly, AI, or hardware contract sections.

- [ ] **Step 5: Record the product-level checkpoint**

Create `docs/PHASE_2_REVIEW.md` with these headings and factual status:

```markdown
# Phase 2 Review — Product Backbone Slice

## What now works
## Caregiver walkthrough
## What survives restart
## Safety and failure checks
## What Rishit can rely on
## What is still deferred inside Phase 2
## Gate decision
```

Mark the slice complete only after the full commands below pass. Keep the overall Phase 2 status `In progress`; this first slice does not close the full frontend/backend/hardware checkpoint.

- [ ] **Step 6: Run focused and full verification**

Run: `python3 -m pytest tests/api tests/persistence -q`

Expected: all API/persistence tests pass.

Run: `python3 -m pytest -q`

Expected: all Phase 1 and Phase 2 tests pass.

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`

Expected: the original 72 unittest tests pass unchanged.

Run: `python3 -m compileall -q backend`

Expected: exit 0.

Run: `git diff --check`

Expected: no output.

- [ ] **Step 7: Run the founder product walkthrough**

Use only synthetic data. Show, in order: resident/room assignment, open event, acknowledge, check, resolve, feedback, resident memory, application restart, recovered event history/memory, invalid transition rejection, same-key replay, conflicting-key rejection, and cross-tenant not-found behavior.

- [ ] **Step 8: Commit the completed first slice**

```bash
git add backend tests docs pyproject.toml alembic.ini .env.example
git commit -m "feat: complete durable phase 2 caregiver journey"
```

- [ ] **Step 9: Review and merge gate**

Push the existing `akshar/backend-phase2-product-backbone` branch, open one pull request, run repository checks and Greptile until 5/5 with zero unresolved actionable threads (maximum five iterations), squash-merge, delete the source branch, and rerun the full suite from merged `main`.
