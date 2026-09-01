from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from backend.app.ai.analysis_contracts import (
    AnalysisRun,
    AnalysisState,
    AttributionScope,
    ConfidenceBand,
    FinalAnalysis,
    Possibility,
    Severity,
)
from backend.app.ai.client import RecommendedDisposition
from backend.app.db.base import Base
from backend.app.db.intelligence_mappers import (
    analysis_run_from_row,
    analysis_run_to_row,
)
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.services.errors import ConcurrentUpdateError
from tests.persistence.test_intelligence_repositories import (
    _anomaly_revision,
    _baseline,
)


AT = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)


def _run(packet, *, evidence_ref: str | None = None) -> AnalysisRun:
    ref = evidence_ref or packet.evidence_refs[0]
    possibility = Possibility(
        possibility_id="possibility_routine",
        label="routine movement",
        confidence=ConfidenceBand.MEDIUM,
        supporting_evidence_refs=(ref,),
        contradicting_evidence_refs=(),
        missing_information=("staff confirmation",),
        rationale="The measured movement may match ordinary activity.",
    )
    final = FinalAnalysis(
        analysis_id="analysis_persisted_1",
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        possibilities=(possibility,),
        severity=Severity.WATCH,
        recommended_disposition=RecommendedDisposition.OBSERVE,
        attribution_scope=AttributionScope.RESIDENT,
        caregiver_summary="Routine movement is plausible.",
        next_step="Observe and review if the pattern continues.",
        missing_information=("staff confirmation",),
        specialist_disagreements=(),
        evidence_refs=(ref,),
        considered_possibility_ids=(possibility.possibility_id,),
        coverage_complete=True,
        model_id="scripted-final",
        model_version="scripted-v1",
        skill_versions=("final-integrator-reviewer-v1",),
    )
    return AnalysisRun(
        analysis_id=final.analysis_id,
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        state=AnalysisState.ANALYZED,
        routing_plan=None,
        specialist_assessments=(),
        unavailable_specialists=(),
        final_analysis=final,
        errors=(),
        repair_count=0,
        input_fingerprint="test-input-fingerprint",
        attempt_number=1,
    )


def test_analysis_mapper_round_trips_canonical_domain_record() -> None:
    _, packet = _anomaly_revision(_baseline())
    run = _run(packet)

    row = analysis_run_to_row("tenant_demo", run, packet, AT)

    assert analysis_run_from_row(row) == run
    assert "prompt" not in row.payload_json.casefold()
    assert "api_key" not in row.payload_json.casefold()


def test_repository_is_idempotent_and_tenant_scoped() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            repository = IntelligenceRepository(session)
            baseline = _baseline()
            update, packet = _anomaly_revision(baseline)
            repository.save_baseline("tenant_demo", baseline, AT)
            repository.save_anomaly_revision("tenant_demo", update, packet)
            run = _run(packet)

            first = repository.save_analysis_run("tenant_demo", run, AT)
            replay = repository.save_analysis_run("tenant_demo", run, AT)

            assert replay == first == run
            assert repository.find_analysis_run("tenant_demo", run.analysis_id) == run
            assert repository.find_analysis_run("tenant_other", run.analysis_id) is None
            assert repository.latest_analysis_run("tenant_demo", packet.anomaly_id) == run
            assert repository.analysis_checkpoints_for_anomaly(
                "tenant_demo", packet.anomaly_id
            ) == (run,)
    finally:
        engine.dispose()


def test_repository_rejects_fabricated_evidence_reference() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            repository = IntelligenceRepository(session)
            baseline = _baseline()
            update, packet = _anomaly_revision(baseline)
            repository.save_baseline("tenant_demo", baseline, AT)
            repository.save_anomaly_revision("tenant_demo", update, packet)

            with pytest.raises(ValueError, match="outside its anomaly packet"):
                repository.save_analysis_run(
                    "tenant_demo",
                    _run(packet, evidence_ref="evidence://fabricated/1/value"),
                    AT,
                )
    finally:
        engine.dispose()


def test_same_anomaly_revision_keeps_append_only_attempts_and_returns_latest() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            seed_synthetic_story(session)
            repository = IntelligenceRepository(session)
            baseline = _baseline()
            update, packet = _anomaly_revision(baseline)
            repository.save_baseline("tenant_demo", baseline, AT)
            repository.save_anomaly_revision("tenant_demo", update, packet)
            run = _run(packet)
            repository.save_analysis_run("tenant_demo", run, AT)

            second = replace(
                run,
                analysis_id="analysis_attempt_2",
                attempt_number=2,
                final_analysis=replace(
                    run.final_analysis,
                    analysis_id="analysis_attempt_2",
                ),
            )
            repository.save_analysis_run(
                "tenant_demo",
                second,
                AT + timedelta(seconds=1),
            )

            assert repository.find_analysis_run("tenant_demo", run.analysis_id) == run
            assert repository.analysis_for_revision(
                "tenant_demo", packet.anomaly_id, packet.packet_revision
            ) == second
            assert repository.analysis_checkpoints_for_anomaly(
                "tenant_demo", packet.anomaly_id
            ) == (second,)
    finally:
        engine.dispose()
