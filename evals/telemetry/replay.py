"""Run isolated device-shaped scenarios through the production ingest boundary."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.models import (
    AnomalyRevisionRow,
    DeviceRoomAssignmentRow,
    EdgeTelemetryRow,
    FusedFrameRow,
    MonitoringEventRow,
    NormalizedObservationRow,
    RoomRow,
)
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.db.status_mappers import StoredMonitoringStatus
from backend.app.db.status_repositories import MonitoringStatusRepository
from backend.app.domain.monitoring import PresenceState, derive_monitoring_snapshot
from backend.app.intelligence.baseline import BaselineSnapshot, FeatureBaseline
from backend.app.main import create_app
from evals.telemetry.scenarios import TelemetryScenario


EVAL_START = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
_KEY = "deterministic-telemetry-eval-key"
_HEADERS = {"Authorization": f"Bearer {_KEY}"}


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    family: str
    passed: bool
    issues: tuple[str, ...]
    request_statuses: tuple[int, ...]
    processing_states: tuple[str, ...]
    accepted_packets: int
    duplicate_packets: int
    conflicts: int
    raw_packets: int
    observations: int
    frames: int
    feature_names: tuple[str, ...]
    missing_sources: tuple[str, ...]
    assignment_blocked: bool
    anomaly_detected: bool
    event_created: bool
    sequence_gap_detected: bool
    replay_idempotent: bool
    latency_ms: float

    def stable_data(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("latency_ms")
        return data


@dataclass(frozen=True)
class ReplaySummary:
    total_cases: int
    passed_cases: int
    failed_cases: int
    accepted_packets: int
    duplicate_packets: int
    rejected_requests: int
    expected_conflicts: int
    expected_conflicts_detected: int
    expected_assignment_blocks: int
    assignment_blocks_detected: int
    feature_mapping_failures: int
    supported_anomaly_recall: float
    normal_false_event_rate: float
    replay_idempotency_failures: int
    median_case_latency_ms: float
    p95_case_latency_ms: float

    def stable_data(self) -> dict[str, object]:
        data = asdict(self)
        data.pop("median_case_latency_ms")
        data.pop("p95_case_latency_ms")
        return data


@dataclass(frozen=True)
class ReplayResult:
    summary: ReplaySummary
    cases: tuple[ScenarioResult, ...]

    def stable_data(self) -> dict[str, object]:
        return {
            "summary": self.summary.stable_data(),
            "cases": [item.stable_data() for item in self.cases],
        }

    def write(self, output: Path) -> None:
        output.mkdir(parents=True, exist_ok=True)
        (output / "results.json").write_text(
            json.dumps([asdict(item) for item in self.cases], indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        (output / "summary.json").write_text(
            json.dumps(asdict(self.summary), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (output / "report.md").write_text(_report(self), encoding="utf-8")


def run_replay(suite: tuple[TelemetryScenario, ...]) -> ReplayResult:
    results = tuple(_run_scenario(scenario) for scenario in suite)
    expected_anomalies = tuple(
        result
        for scenario, result in zip(suite, results, strict=True)
        if scenario.expected_anomaly
    )
    normal_cases = tuple(
        result
        for scenario, result in zip(suite, results, strict=True)
        if scenario.expected_event is False
    )
    latencies = sorted(item.latency_ms for item in results)
    p95_index = max(0, min(len(latencies) - 1, round(0.95 * len(latencies)) - 1))
    summary = ReplaySummary(
        total_cases=len(results),
        passed_cases=sum(item.passed for item in results),
        failed_cases=sum(not item.passed for item in results),
        accepted_packets=sum(item.accepted_packets for item in results),
        duplicate_packets=sum(item.duplicate_packets for item in results),
        rejected_requests=sum(item.conflicts for item in results),
        expected_conflicts=sum(item.expected_conflict for item in suite),
        expected_conflicts_detected=sum(
            scenario.expected_conflict and result.conflicts > 0
            for scenario, result in zip(suite, results, strict=True)
        ),
        expected_assignment_blocks=sum(
            item.expected_assignment_block for item in suite
        ),
        assignment_blocks_detected=sum(
            scenario.expected_assignment_block and result.assignment_blocked
            for scenario, result in zip(suite, results, strict=True)
        ),
        feature_mapping_failures=sum(
            not set(scenario.expected_features) <= set(result.feature_names)
            for scenario, result in zip(suite, results, strict=True)
        ),
        supported_anomaly_recall=(
            1.0
            if not expected_anomalies
            else sum(item.anomaly_detected for item in expected_anomalies)
            / len(expected_anomalies)
        ),
        normal_false_event_rate=(
            0.0
            if not normal_cases
            else sum(item.event_created for item in normal_cases) / len(normal_cases)
        ),
        replay_idempotency_failures=sum(
            scenario.expected_duplicate and not result.replay_idempotent
            for scenario, result in zip(suite, results, strict=True)
        ),
        median_case_latency_ms=round(median(latencies), 3) if latencies else 0.0,
        p95_case_latency_ms=round(latencies[p95_index], 3) if latencies else 0.0,
    )
    return ReplayResult(summary, results)


def _run_scenario(scenario: TelemetryScenario) -> ScenarioResult:
    started = perf_counter()
    with TemporaryDirectory(prefix="telemetry-eval-") as directory:
        database_url = f"sqlite+pysqlite:///{Path(directory) / 'scenario.db'}"
        database_engine = create_engine_for_url(database_url)
        Base.metadata.create_all(database_engine)
        with Session(database_engine) as session:
            seed_synthetic_story(session)
            session.add(
                RoomRow(
                    room_id="room_spare",
                    tenant_id="tenant_demo",
                    label="Spare room",
                )
            )
            if scenario.baseline is not None:
                baseline = scenario.baseline
                IntelligenceRepository(session).save_baseline(
                    "tenant_demo",
                    BaselineSnapshot(
                        baseline_id=f"baseline_{scenario.scenario_id}",
                        resident_id="resident_demo_a",
                        monitoring_setup_version="setup_room_214_v1",
                        features=(
                            FeatureBaseline(
                                feature_name=baseline.feature_name,
                                purpose=baseline.purpose,
                                median=baseline.median,
                                mad=baseline.mad,
                                iqr=baseline.iqr,
                                lower_quantile=baseline.lower_quantile,
                                upper_quantile=baseline.upper_quantile,
                                resolution_floor=baseline.resolution_floor,
                                unit=baseline.unit,
                                eligible_sample_count=20,
                                context_key="resident_global",
                            ),
                        ),
                        policy_version="synthetic_baseline_v1",
                    ),
                    EVAL_START - timedelta(minutes=1),
                )
            if scenario.assignment_mode == "missing":
                assignment = session.get(
                    DeviceRoomAssignmentRow,
                    "device_assign_room_214",
                )
                if assignment is None:
                    raise RuntimeError("seed device assignment missing")
                assignment.status = "inactive"
                assignment.effective_to = EVAL_START
            if scenario.presence != PresenceState.RESIDENT_PRESENT.value:
                presence = PresenceState(scenario.presence)
                MonitoringStatusRepository(session).record(
                    "tenant_demo",
                    StoredMonitoringStatus(
                        resident_id="resident_demo_a",
                        room_id="room_214",
                        observed_at=EVAL_START - timedelta(seconds=1),
                        snapshot=derive_monitoring_snapshot(
                            assignment_valid=True,
                            device_healthy=True,
                            presence=presence,
                            signal_quality=0.9,
                        ),
                    ),
                )
            session.commit()
        database_engine.dispose()

        app = create_app(
            Settings(
                app_env="test",
                database_url=database_url,
                ingest_bearer_key=_KEY,
                ingest_tenant_id="tenant_demo",
            )
        )
        ticks = count()
        app.state.telemetry_clock = lambda: EVAL_START + timedelta(
            seconds=5 * next(ticks)
        )
        responses = []
        with TestClient(app) as client:
            for payload in scenario.capture_payloads:
                responses.append(
                    client.post(
                        "/v1/ingest/telemetry",
                        json=payload,
                        headers=_HEADERS,
                    )
                )

            with Session(app.state.engine) as session:
                raw_packets = int(
                    session.scalar(select(func.count()).select_from(EdgeTelemetryRow))
                    or 0
                )
                observations = session.scalars(
                    select(NormalizedObservationRow)
                ).all()
                frames = session.scalars(select(FusedFrameRow)).all()
                anomaly_count = int(
                    session.scalar(
                        select(func.count()).select_from(AnomalyRevisionRow)
                    )
                    or 0
                )
                event_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(MonitoringEventRow)
                        .where(MonitoringEventRow.source_anomaly_id.is_not(None))
                    )
                    or 0
                )
                gap_count = int(
                    session.scalar(
                        select(func.count())
                        .select_from(EdgeTelemetryRow)
                        .where(EdgeTelemetryRow.sequence_gap > 0)
                    )
                    or 0
                )

        request_statuses = tuple(response.status_code for response in responses)
        bodies = tuple(
            response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            for response in responses
        )
        processing_states = tuple(
            body["processing_state"]
            for response, body in zip(responses, bodies, strict=True)
            if response.status_code == 202
        )
        accepted_packets = sum(
            int(body.get("accepted", 0))
            for response, body in zip(responses, bodies, strict=True)
            if response.status_code == 202
        )
        duplicate_packets = sum(
            int(body.get("duplicate_count", 0))
            for response, body in zip(responses, bodies, strict=True)
            if response.status_code == 202
        )
        conflicts = sum(response.status_code == 409 for response in responses)
        feature_names = tuple(
            sorted(
                {
                    feature["name"]
                    for row in observations
                    for feature in row.observation["features"]
                }
            )
        )
        missing_sources = tuple(
            sorted(
                {
                    source
                    for row in frames
                    for source in row.frame["sources_missing"]
                }
            )
        )
        assignment_blocked = "blocked" in processing_states
        anomaly_detected = anomaly_count > 0
        event_created = event_count > 0
        sequence_gap_detected = gap_count > 0
        first_capture_size = len(scenario.capture_payloads[0])
        replay_idempotent = (
            not scenario.expected_duplicate or raw_packets == first_capture_size
        )

        issues: list[str] = []
        if any(status not in {202, 409} for status in request_statuses):
            issues.append("unexpected_http_status")
        if scenario.expected_duplicate != (duplicate_packets > 0):
            issues.append("duplicate_expectation_mismatch")
        if scenario.expected_conflict != (conflicts > 0):
            issues.append("conflict_expectation_mismatch")
        if scenario.expected_assignment_block != assignment_blocked:
            issues.append("assignment_expectation_mismatch")
        if scenario.expected_anomaly != anomaly_detected:
            issues.append("anomaly_expectation_mismatch")
        if scenario.expected_event is not None and scenario.expected_event != event_created:
            issues.append("event_expectation_mismatch")
        if not set(scenario.expected_features) <= set(feature_names):
            issues.append("feature_mapping_missing")
        if not set(scenario.expected_missing_sources) <= set(missing_sources):
            issues.append("missing_source_not_recorded")
        if scenario.expected_sequence_gap != sequence_gap_detected:
            issues.append("sequence_gap_expectation_mismatch")
        if not replay_idempotent:
            issues.append("retry_duplicated_packets")

        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            family=scenario.family,
            passed=not issues,
            issues=tuple(issues),
            request_statuses=request_statuses,
            processing_states=processing_states,
            accepted_packets=accepted_packets,
            duplicate_packets=duplicate_packets,
            conflicts=conflicts,
            raw_packets=raw_packets,
            observations=len(observations),
            frames=len(frames),
            feature_names=feature_names,
            missing_sources=missing_sources,
            assignment_blocked=assignment_blocked,
            anomaly_detected=anomaly_detected,
            event_created=event_created,
            sequence_gap_detected=sequence_gap_detected,
            replay_idempotent=replay_idempotent,
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )


def _report(result: ReplayResult) -> str:
    summary = result.summary
    failing = [item for item in result.cases if not item.passed]
    lines = [
        "# Telemetry Pipeline Replay Report",
        "",
        "This report exercises device-shaped radar, thermal, and Wi-Fi CSI payloads through the production ingestion and intelligence boundary. All thresholds and sensor inputs are synthetic engineering fixtures, not clinical validation.",
        "",
        "## Results",
        "",
        f"- Cases: {summary.total_cases}",
        f"- Passed: {summary.passed_cases}",
        f"- Failed: {summary.failed_cases}",
        f"- Accepted packets: {summary.accepted_packets}",
        f"- Duplicate packets safely ignored: {summary.duplicate_packets}",
        f"- Expected conflicts detected: {summary.expected_conflicts_detected}/{summary.expected_conflicts}",
        f"- Assignment blocks detected: {summary.assignment_blocks_detected}/{summary.expected_assignment_blocks}",
        f"- Supported anomaly recall: {summary.supported_anomaly_recall:.1%}",
        f"- Normal false-event rate: {summary.normal_false_event_rate:.1%}",
        f"- Median case latency: {summary.median_case_latency_ms:.3f} ms",
        f"- P95 case latency: {summary.p95_case_latency_ms:.3f} ms",
        "",
        "## Interpretation",
        "",
        "The replay proves the software contract, durability, assignment gate, source normalization, fusion, synthetic anomaly path, event idempotency, and restart behavior with controlled data. It does not prove real-sensor accuracy, production calibration thresholds, clinical meaning, or deployment readiness.",
    ]
    if failing:
        lines.extend(("", "## Failures", ""))
        lines.extend(
            f"- `{item.scenario_id}`: {', '.join(item.issues)}"
            for item in failing
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "ReplayResult",
    "ReplaySummary",
    "ScenarioResult",
    "run_replay",
]
