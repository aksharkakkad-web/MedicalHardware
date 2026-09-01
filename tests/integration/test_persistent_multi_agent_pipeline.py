from dataclasses import replace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.repositories import EventRepository, FeedbackRepository, ResidentRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.models import DispositionDecisionRow, MultiAgentAnalysisRow
from backend.app.db.session import create_engine_for_url
from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine
from backend.app.services.monitoring_processing import PersistentMonitoringService
from backend.app.services.event_queue import EventQueueQuery, ProductEventQueueQueryService
from backend.app.services.queries import AccessContext, ProductQueryService
from tests.intelligence.test_multi_agent_monitoring_flow import _ScriptedOrchestrator, _run
from tests.intelligence.test_policy_orchestration import (
    _baseline,
    _fall_sequence,
    _memory,
    _movement_frame,
)
from backend.app.ai.analysis_contracts import AnalysisState, Severity
from backend.app.ai.analysis_orchestration import MultiAgentAnalysisOrchestrator
from backend.app.ai.client import RecommendedDisposition
from backend.app.services.errors import ConcurrentUpdateError
from evals.monitoring.scripted_analysis import ScriptedAnalysisClient


class _ExplodingOrchestrator(MultiAgentAnalysisOrchestrator):
    def _analyze_locked(self, *args, **kwargs):
        raise RuntimeError("synthetic unexpected orchestration failure")


def test_process_persist_restart_and_dashboard_read_keep_exact_analysis() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            monitoring = MonitoringIntelligenceEngine(
                analysis_orchestrator=_ScriptedOrchestrator(
                    _run(RecommendedDisposition.CAREGIVER_EVENT, Severity.HIGH)
                )
            )
            service = PersistentMonitoringService(session, monitoring)
            result = None
            for second in range(3):
                result = service.process_frame(
                    _movement_frame(second, 0.5),
                    baseline=_baseline(),
                    context_key="resident_global",
                    anomaly_id="anomaly_persisted_flow",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
            assert result is not None and result.event is not None
            event_id = result.event.event_id
            analysis_id = result.analysis.analysis_id
            session.commit()

        with Session(engine) as restarted_session:
            queries = ProductQueryService(
                ResidentRepository(restarted_session),
                EventRepository(restarted_session),
                FeedbackRepository(restarted_session),
                IntelligenceRepository(restarted_session),
            )
            context = AccessContext("tenant_demo", "operator_1")
            event = queries.get_event(context, event_id)
            history = queries.list_resident_analyses(context, "resident_demo_a")
            queue = ProductEventQueueQueryService(
                EventRepository(restarted_session),
                IntelligenceRepository(restarted_session),
            ).list_events(context, EventQueueQuery())

            assert event.analysis is not None
            assert event.analysis.analysis_id == analysis_id
            assert history.items[0].analysis.analysis_id == analysis_id
            assert history.items[0].anomaly_id == "anomaly_persisted_flow"
            queued = next(item for item in queue.items if item.event_id == event_id)
            assert queued.analysis is not None
            assert queued.analysis.analysis_id == analysis_id
    finally:
        engine.dispose()


def test_fall_like_evidence_and_disposition_persist_without_fake_anomaly_row() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            service = PersistentMonitoringService(
                session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=_ScriptedOrchestrator(
                        _run(
                            RecommendedDisposition.CAREGIVER_EVENT,
                            Severity.CRITICAL,
                        )
                    )
                ),
            )
            result = None
            for frame in _fall_sequence():
                result = service.process_frame(
                    frame,
                    baseline=_baseline(feature_name="unused"),
                    context_key="resident_global",
                    anomaly_id="fall_like_persisted",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
            session.flush()

            assert result is not None and result.fall_assessment.urgent_triggered
            assert session.scalar(select(func.count()).select_from(MultiAgentAnalysisRow)) == 1
            assert session.scalar(select(func.count()).select_from(DispositionDecisionRow)) == 1
    finally:
        engine.dispose()


def test_pending_analysis_recovers_as_attempt_two_after_process_restart() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            unavailable = ScriptedAnalysisClient("final_unavailable")
            service = PersistentMonitoringService(
                session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=MultiAgentAnalysisOrchestrator(
                        recall_client=unavailable,
                        precision_client=unavailable,
                        final_client=unavailable,
                    )
                ),
            )
            pending = None
            for second in range(3):
                pending = service.process_frame(
                    _movement_frame(second, 0.5),
                    baseline=_baseline(),
                    context_key="resident_global",
                    anomaly_id="anomaly_restart_retry",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
            assert pending is not None and pending.analysis is not None
            assert pending.analysis.state is AnalysisState.ANALYSIS_PENDING
            assert pending.analysis.attempt_number == 1
            pending_id = pending.analysis.analysis_id
            pending_disposition = session.scalar(
                select(DispositionDecisionRow).where(
                    DispositionDecisionRow.analysis_id == pending_id
                )
            )
            assert pending_disposition is not None
            session.commit()

        with Session(engine) as restarted_session:
            complete = ScriptedAnalysisClient()
            service = PersistentMonitoringService(
                restarted_session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=MultiAgentAnalysisOrchestrator(
                        recall_client=complete,
                        precision_client=complete,
                        final_client=complete,
                    )
                ),
            )
            recovered = None
            for second in range(3):
                recovered = service.process_frame(
                    _movement_frame(second, 0.5),
                    baseline=_baseline(),
                    context_key="resident_global",
                    anomaly_id="anomaly_restart_retry",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
            assert recovered is not None and recovered.analysis is not None
            assert recovered.analysis.state is AnalysisState.ANALYZED
            assert recovered.analysis.attempt_number == 2
            assert recovered.analysis.analysis_id != pending_id
            assert [call.stage.value for call in complete.calls] == ["final"]
            assert restarted_session.scalar(
                select(func.count()).select_from(MultiAgentAnalysisRow)
            ) == 2
            latest = IntelligenceRepository(restarted_session).latest_analysis_run(
                "tenant_demo", "anomaly_restart_retry"
            )
            assert latest is not None
            assert latest.analysis_id == recovered.analysis.analysis_id
            assert latest.state is AnalysisState.ANALYZED
            assert latest.attempt_number == 2
            assert all(
                item.payload_json in (None, "{}")
                for item in latest.stage_responses
            )
    finally:
        engine.dispose()


def test_restart_replay_hydrates_every_persisted_packet_checkpoint() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            complete = ScriptedAnalysisClient()
            service = PersistentMonitoringService(
                session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=MultiAgentAnalysisOrchestrator(
                        recall_client=complete,
                        precision_client=complete,
                        final_client=complete,
                    )
                ),
            )
            for second in range(7):
                service.process_frame(
                    _movement_frame(second, 0.5),
                    baseline=_baseline(),
                    context_key="resident_global",
                    anomaly_id="anomaly_multi_revision_restart",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
            original_count = session.scalar(
                select(func.count()).select_from(MultiAgentAnalysisRow)
            )
            assert original_count is not None and original_count > 1
            session.commit()

        with Session(engine) as restarted_session:
            unavailable = ScriptedAnalysisClient("final_unavailable")
            replay = PersistentMonitoringService(
                restarted_session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=MultiAgentAnalysisOrchestrator(
                        recall_client=unavailable,
                        precision_client=unavailable,
                        final_client=unavailable,
                    )
                ),
            )
            for second in range(7):
                result = replay.process_frame(
                    _movement_frame(second, 0.5),
                    baseline=_baseline(),
                    context_key="resident_global",
                    anomaly_id="anomaly_multi_revision_restart",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
                if result.analysis is not None:
                    assert result.analysis.state is AnalysisState.ANALYZED
            assert unavailable.calls == []
            assert restarted_session.scalar(
                select(func.count()).select_from(MultiAgentAnalysisRow)
            ) == original_count
    finally:
        engine.dispose()


def test_pending_fall_analysis_persists_without_a_normal_anomaly_revision() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            unavailable = ScriptedAnalysisClient("final_unavailable")
            service = PersistentMonitoringService(
                session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=MultiAgentAnalysisOrchestrator(
                        recall_client=unavailable,
                        precision_client=unavailable,
                        final_client=unavailable,
                    )
                ),
            )
            result = None
            for frame in _fall_sequence():
                result = service.process_frame(
                    frame,
                    baseline=_baseline(feature_name="unused"),
                    context_key="resident_global",
                    anomaly_id="fall_pending_persisted",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
            session.flush()

            assert result is not None and result.analysis is not None
            assert result.analysis.state is AnalysisState.ANALYSIS_PENDING
            assert result.event is not None
            assert result.event.priority.value == "critical"
            assert result.decision.disposition.value == "caregiver_event"
            assert result.decision.fallback_used
            disposition = session.scalar(select(DispositionDecisionRow))
            assert disposition is not None
            assert disposition.analysis_id == result.analysis.analysis_id
            assert session.scalar(
                select(func.count()).select_from(MultiAgentAnalysisRow)
            ) == 1
    finally:
        engine.dispose()


def test_unexpected_orchestration_failure_is_saved_as_visible_pending_history() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            provider = ScriptedAnalysisClient()
            service = PersistentMonitoringService(
                session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=_ExplodingOrchestrator(
                        recall_client=provider,
                        precision_client=provider,
                        final_client=provider,
                    )
                ),
            )
            result = None
            for second in range(3):
                result = service.process_frame(
                    _movement_frame(second, 0.5),
                    baseline=_baseline(),
                    context_key="resident_global",
                    anomaly_id="anomaly_unexpected_failure",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                    resident_memory=_memory("resident_demo_a"),
                )
            assert result is not None and result.analysis is not None
            assert result.analysis.state is AnalysisState.ANALYSIS_PENDING
            assert "analysis_unavailable:RuntimeError" in result.analysis.errors
            session.commit()

        with Session(engine) as restarted_session:
            history = ProductQueryService(
                ResidentRepository(restarted_session),
                EventRepository(restarted_session),
                FeedbackRepository(restarted_session),
                IntelligenceRepository(restarted_session),
            ).list_resident_analyses(
                AccessContext("tenant_demo", "operator_1"),
                "resident_demo_a",
            )
            assert history.items[0].analysis.state is AnalysisState.ANALYSIS_PENDING
            assert history.items[0].analysis.analysis_id == result.analysis.analysis_id
    finally:
        engine.dispose()


def test_persistent_multi_agent_service_requires_memory_before_consuming_frame() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            provider = ScriptedAnalysisClient()
            service = PersistentMonitoringService(
                session,
                MonitoringIntelligenceEngine(
                    analysis_orchestrator=MultiAgentAnalysisOrchestrator(
                        recall_client=provider,
                        precision_client=provider,
                        final_client=provider,
                    )
                ),
            )

            with pytest.raises(ValueError, match="resident_memory is required"):
                service.process_frame(
                    _movement_frame(0, 0.5),
                    baseline=_baseline(),
                    context_key="resident_global",
                    anomaly_id="anomaly_missing_memory",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                )

            assert IntelligenceRepository(session).latest_baseline(
                "tenant_demo", "resident_demo_a"
            ) is None
            assert provider.calls == []
    finally:
        engine.dispose()


def test_reused_baseline_id_with_changed_contents_is_rejected_before_processing() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            service = PersistentMonitoringService(session, MonitoringIntelligenceEngine())
            baseline = _baseline()
            service.process_frame(
                _movement_frame(0, 0.0),
                baseline=baseline,
                context_key="resident_global",
                anomaly_id="anomaly_baseline_lineage",
                tenant_id="tenant_demo",
                resident_id="resident_demo_a",
                room_id="room_214",
                config_version="test_config_v1",
                unknowns=("cause",),
            )

            with pytest.raises(ConcurrentUpdateError, match="baseline identity"):
                service.process_frame(
                    _movement_frame(1, 0.0),
                    baseline=replace(baseline, policy_version="changed_policy"),
                    context_key="resident_global",
                    anomaly_id="anomaly_baseline_lineage",
                    tenant_id="tenant_demo",
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    config_version="test_config_v1",
                    unknowns=("cause",),
                )
    finally:
        engine.dispose()
