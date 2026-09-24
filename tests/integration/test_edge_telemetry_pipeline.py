import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.ai.client import RecommendedDisposition
from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.models import (
    DeviceRoomAssignmentRow,
    EdgeTelemetryRow,
    MonitoringEventRow,
    NormalizedObservationRow,
)
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.db.telemetry_repositories import TelemetryRepository
from backend.app.intelligence import FeaturePurpose
from backend.app.intelligence.baseline import BaselineSnapshot, FeatureBaseline
from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine
from backend.app.main import create_app
from backend.app.services.telemetry_processing import TelemetryProcessingCoordinator
from tests.intelligence.test_multi_agent_monitoring_flow import (
    _run,
)
from backend.app.ai.analysis_contracts import Severity


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "edge_telemetry"
    / "mahin_capture_v1.json"
)
KEY = "integration-ingest-key"
HEADERS = {"Authorization": f"Bearer {KEY}"}
NOW = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)


class _PipelineOrchestrator:
    def __init__(self) -> None:
        self.checkpoints = {}

    def analyze(
        self,
        packet,
        resident_memory,
        relevant_context_entry_ids=(),
        *,
        tenant_id,
    ):
        result = _run(
            RecommendedDisposition.CAREGIVER_EVENT,
            Severity.HIGH,
            packet=packet,
        )
        analysis_id = f"analysis_{packet.anomaly_id}_{packet.packet_revision}"
        result = replace(
            result,
            analysis_id=analysis_id,
            final_analysis=replace(result.final_analysis, analysis_id=analysis_id),
            input_fingerprint=f"pipeline:{tenant_id}:{packet.anomaly_id}:{packet.packet_revision}",
        )
        self.checkpoints[result.input_fingerprint] = result
        return result

    def restore_checkpoint(self, run) -> None:
        existing = self.checkpoints.get(run.input_fingerprint)
        if existing is not None and existing != run:
            raise ValueError("checkpoint conflict")
        self.checkpoints[run.input_fingerprint] = run


def _capture(
    *,
    sequence: int = 1,
    sources: tuple[str, ...] = ("radar", "thermal", "wifi_csi"),
    movement: float | None = None,
) -> list[dict[str, object]]:
    capture = []
    for item in json.loads(FIXTURE.read_text()):
        if item["source"] not in sources:
            continue
        item["stream_id"] = "integration-stream"
        item["sequence"] = sequence
        item["transport"] = {
            "batch_id": f"integration-{sequence}-{item['source']}",
            "retry_count": 0,
        }
        if movement is not None and item["source"] in {"radar", "wifi_csi"}:
            item["payload"]["movement_score"] = movement
        capture.append(item)
    return capture


def _baseline() -> BaselineSnapshot:
    return BaselineSnapshot(
        baseline_id="baseline_edge_integration",
        resident_id="resident_demo_a",
        monitoring_setup_version="setup_room_214_v1",
        features=(
            FeatureBaseline(
                feature_name="movement_energy",
                purpose=FeaturePurpose.MOVEMENT,
                median=0.1,
                mad=0.02,
                iqr=0.05,
                lower_quantile=0.05,
                upper_quantile=0.2,
                resolution_floor=0.05,
                unit="normalized",
                eligible_sample_count=20,
                context_key="resident_global",
            ),
        ),
        policy_version="synthetic_baseline_v1",
    )


def _make_app(tmp_path, *, baseline: bool = False):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'edge-pipeline.db'}"
    engine = create_engine_for_url(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_synthetic_story(session)
        if baseline:
            IntelligenceRepository(session).save_baseline(
                "tenant_demo",
                _baseline(),
                NOW,
            )
        session.commit()
    engine.dispose()
    app = create_app(
        Settings(
            app_env="test",
            database_url=database_url,
            ingest_bearer_key=KEY,
            ingest_tenant_id="tenant_demo",
        )
    )
    ticks = count()
    app.state.telemetry_clock = lambda: NOW + timedelta(
        seconds=5 * next(ticks)
    )
    return app


def _count(session: Session, row_type: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(row_type)) or 0)


def test_capture_normalizes_fuses_and_waits_honestly_for_baseline(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/v1/ingest/telemetry",
            json=_capture(),
            headers=HEADERS,
        )

        assert response.status_code == 202
        assert response.json()["processing_state"] == "calibrating"
        batch_id = response.json()["batch_id"]
        with Session(app.state.engine) as session:
            repository = TelemetryRepository(session)
            frame = repository.frame_for_batch(batch_id)
            assert frame is not None
            assert frame.sources_present == ("radar", "thermal", "wifi_csi")
            assert frame.sources_missing == ()
            assert len(repository.observations_for_batch(batch_id)) == 3
            assert _count(session, EdgeTelemetryRow) == 3


def test_missing_source_remains_explicit_in_fused_frame(tmp_path) -> None:
    app = _make_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/v1/ingest/telemetry",
            json=_capture(sources=("radar", "thermal")),
            headers=HEADERS,
        )
        with Session(app.state.engine) as session:
            frame = TelemetryRepository(session).frame_for_batch(
                response.json()["batch_id"]
            )

    assert response.status_code == 202
    assert frame is not None
    assert frame.sources_present == ("radar", "thermal")
    assert frame.sources_missing == ("wifi_csi",)


def test_assignment_mismatch_keeps_raw_data_but_creates_no_resident_frame(
    tmp_path,
) -> None:
    app = _make_app(tmp_path)
    with Session(app.state.engine) as session:
        assignment = session.get(
            DeviceRoomAssignmentRow,
            "device_assign_room_214",
        )
        assert assignment is not None
        assignment.status = "inactive"
        assignment.effective_to = NOW
        session.commit()

    with TestClient(app) as client:
        response = client.post(
            "/v1/ingest/telemetry",
            json=_capture(),
            headers=HEADERS,
        )
        with Session(app.state.engine) as session:
            repository = TelemetryRepository(session)
            batch_id = response.json()["batch_id"]
            assert repository.frame_for_batch(batch_id) is None
            assert repository.observations_for_batch(batch_id) == ()
            assert _count(session, EdgeTelemetryRow) == 3

    assert response.status_code == 202
    assert response.json()["processing_state"] == "blocked"


def test_established_baseline_runs_anomaly_ai_and_event_path(tmp_path) -> None:
    app = _make_app(tmp_path, baseline=True)
    app.state.monitoring_engine = MonitoringIntelligenceEngine(
        analysis_orchestrator=_PipelineOrchestrator()
    )

    with TestClient(app) as client:
        responses = [
            client.post(
                "/v1/ingest/telemetry",
                json=_capture(sequence=sequence, movement=0.95),
                headers=HEADERS,
            )
            for sequence in (1, 2, 3)
        ]

        assert all(response.status_code == 202 for response in responses)
        assert all(
            response.json()["processing_state"] == "processed"
            for response in responses
        )
        with Session(app.state.engine) as session:
            generated = session.scalars(
                select(MonitoringEventRow).where(
                    MonitoringEventRow.source_anomaly_id.is_not(None),
                    MonitoringEventRow.source_anomaly_id != "",
                    MonitoringEventRow.event_id != "evt_phase2_demo",
                )
            ).all()
            assert len(generated) == 1
            assert generated[0].priority == "high"


def test_restart_replay_does_not_duplicate_event(tmp_path) -> None:
    app = _make_app(tmp_path, baseline=True)
    app.state.monitoring_engine = MonitoringIntelligenceEngine(
        analysis_orchestrator=_PipelineOrchestrator()
    )
    with TestClient(app) as client:
        responses = [
            client.post(
                "/v1/ingest/telemetry",
                json=_capture(sequence=sequence, movement=0.95),
                headers=HEADERS,
            )
            for sequence in (1, 2, 3)
        ]

    restarted = create_app(app.state.settings)
    restarted.state.monitoring_engine = MonitoringIntelligenceEngine(
        analysis_orchestrator=_PipelineOrchestrator()
    )
    restarted.state.telemetry_clock = lambda: NOW + timedelta(seconds=15)
    with TestClient(restarted) as client:
        continuation = client.post(
            "/v1/ingest/telemetry",
            json=_capture(sequence=4, movement=0.95),
            headers=HEADERS,
        )
        assert continuation.status_code == 202
        assert continuation.json()["processing_state"] == "processed"
        with Session(restarted.state.engine) as session:
            generated = session.scalars(
                select(MonitoringEventRow).where(
                    MonitoringEventRow.event_id != "evt_phase2_demo"
                )
            ).all()
            assert len(generated) == 1
            assert generated[0].signal_count == 2


class _FailingEngine(MonitoringIntelligenceEngine):
    def process_frame(self, *args, **kwargs):
        raise RuntimeError("synthetic processing failure")


def test_processing_failure_keeps_raw_capture_replayable(tmp_path) -> None:
    app = _make_app(tmp_path, baseline=True)
    app.state.monitoring_engine = _FailingEngine()
    with TestClient(app) as client:
        response = client.post(
            "/v1/ingest/telemetry",
            json=_capture(movement=0.95),
            headers=HEADERS,
        )

    assert response.status_code == 202
    assert response.json()["processing_state"] == "failed"
    with Session(app.state.engine) as session:
        assert _count(session, EdgeTelemetryRow) == 3
        assert _count(session, NormalizedObservationRow) == 0
        coordinator = TelemetryProcessingCoordinator(
            session,
            MonitoringIntelligenceEngine(),
        )
        replayed = coordinator.drain_pending(limit=10)
        session.commit()
        assert [item.processing_state for item in replayed] == ["processed"]
