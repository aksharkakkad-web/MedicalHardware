import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.contracts.ingestion import (
    DeviceHeartbeatRequest,
    TelemetryCaptureRequest,
)
from backend.app.db.base import Base
from backend.app.db.models import (
    DeviceHeartbeatIdentityRow,
    EdgeTelemetryRow,
    FusedFrameRow,
    NormalizedObservationRow,
    TelemetryCaptureBatchRow,
)
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.db.telemetry_repositories import (
    HeartbeatRepository,
    TelemetryRepository,
)
from backend.app.intelligence.fusion import align_observations
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    NormalizedObservation,
    QualityClass,
)
from backend.app.services.errors import ConcurrentUpdateError


NOW = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "edge_telemetry"
    / "mahin_capture_v1.json"
)


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as active:
        seed_synthetic_story(active)
        active.commit()
        yield active
    engine.dispose()


def _raw_capture() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text())


def _capture(raw: object | None = None) -> TelemetryCaptureRequest:
    return TelemetryCaptureRequest.model_validate(
        _raw_capture() if raw is None else raw
    )


def _single_radar(
    *,
    sequence: int,
    stream_id: str = "legacy",
    payload: dict[str, object] | None = None,
) -> TelemetryCaptureRequest:
    raw = deepcopy(_raw_capture()[0])
    raw["sequence"] = sequence
    raw["stream_id"] = stream_id
    raw["transport"] = {
        "batch_id": f"radar-{stream_id}-{sequence}",
        "retry_count": 0,
    }
    if payload is not None:
        raw["payload"] = payload
    return _capture(raw)


def _count(session: Session, row_type: type[object]) -> int:
    return int(session.scalar(select(func.count()).select_from(row_type)) or 0)


def test_exact_capture_retry_returns_original_batch(session: Session) -> None:
    repository = TelemetryRepository(session)
    first = repository.save_capture(_capture(), received_at=NOW)
    second = repository.save_capture(
        _capture(),
        received_at=NOW + timedelta(seconds=1),
    )

    assert second.batch_id == first.batch_id
    assert second.duplicate is True
    assert second.received_at == NOW
    assert _count(session, EdgeTelemetryRow) == 3
    assert _count(session, TelemetryCaptureBatchRow) == 1


def test_retry_count_change_is_still_the_same_semantic_capture(
    session: Session,
) -> None:
    repository = TelemetryRepository(session)
    first = repository.save_capture(_capture(), received_at=NOW)
    retried = _raw_capture()
    for item in retried:
        item["transport"]["retry_count"] = 2

    second = repository.save_capture(
        _capture(retried),
        received_at=NOW + timedelta(seconds=1),
    )

    assert second.batch_id == first.batch_id
    assert second.duplicate


def test_changed_duplicate_conflicts(session: Session) -> None:
    repository = TelemetryRepository(session)
    repository.save_capture(_capture(), received_at=NOW)
    changed = _raw_capture()
    changed[0]["payload"]["heart_rate_bpm"] = 81.0

    with pytest.raises(ConcurrentUpdateError):
        repository.save_capture(
            _capture(changed),
            received_at=NOW + timedelta(seconds=1),
        )

    assert _count(session, EdgeTelemetryRow) == 3


def test_new_stream_can_restart_but_same_stream_stale_sequence_is_rejected(
    session: Session,
) -> None:
    repository = TelemetryRepository(session)
    repository.save_capture(_single_radar(sequence=41), received_at=NOW)

    restarted = repository.save_capture(
        _single_radar(sequence=1, stream_id="boot-02"),
        received_at=NOW + timedelta(seconds=1),
    )
    assert restarted.packets[0].sequence == 1
    assert restarted.packets[0].stream_id == "boot-02"

    with pytest.raises(ConcurrentUpdateError):
        repository.save_capture(
            _single_radar(sequence=40),
            received_at=NOW + timedelta(seconds=2),
        )


def test_sequence_gap_is_accepted_and_recorded(session: Session) -> None:
    repository = TelemetryRepository(session)
    repository.save_capture(_single_radar(sequence=41), received_at=NOW)

    result = repository.save_capture(
        _single_radar(sequence=45),
        received_at=NOW + timedelta(seconds=1),
    )

    assert result.packets[0].sequence_gap == 3


def test_capture_conflict_does_not_partially_store_new_source(
    session: Session,
) -> None:
    repository = TelemetryRepository(session)
    repository.save_capture(_capture(), received_at=NOW)
    mixed = _raw_capture()[:2]
    mixed[0]["payload"]["heart_rate_bpm"] = 81.0
    mixed[1]["sequence"] = 39

    with pytest.raises(ConcurrentUpdateError):
        repository.save_capture(
            _capture(mixed),
            received_at=NOW + timedelta(seconds=1),
        )

    assert _count(session, EdgeTelemetryRow) == 3
    assert session.scalar(
        select(func.count()).where(EdgeTelemetryRow.sequence == 39)
    ) == 0


def test_pending_batches_are_oldest_first(session: Session) -> None:
    repository = TelemetryRepository(session)
    first = repository.save_capture(
        _single_radar(sequence=1, stream_id="boot-pending"),
        received_at=NOW,
    )
    second = repository.save_capture(
        _single_radar(sequence=2, stream_id="boot-pending"),
        received_at=NOW + timedelta(seconds=1),
    )

    assert [item.batch_id for item in repository.pending_batches(limit=10)] == [
        first.batch_id,
        second.batch_id,
    ]


def test_observation_and_frame_round_trip(session: Session) -> None:
    repository = TelemetryRepository(session)
    batch = repository.save_capture(_capture(), received_at=NOW)
    observation = NormalizedObservation(
        observation_id="observation_radar_41",
        tenant_id="tenant_demo",
        room_id="room_214",
        resident_id="resident_demo_a",
        device_id="device_room_214",
        source="radar",
        window_start=NOW,
        window_end=NOW + timedelta(seconds=1),
        features=(
            FeatureValue(
                name="movement_energy",
                value=0.2,
                unit="normalized",
                quality_class=QualityClass.GOOD,
                purposes=(FeaturePurpose.MOVEMENT,),
            ),
        ),
        source_quality_class=QualityClass.GOOD,
        source_quality_reasons=(),
        processor_version="radar_normalizer_v1",
    )
    frame = align_observations(
        (observation,),
        frame_id="frame_capture_1",
        window_start=NOW,
        window_end=NOW + timedelta(seconds=1),
        expected_sources=("radar", "thermal", "wifi_csi"),
    )

    stored_observation = repository.save_observation(batch.batch_id, observation)
    stored_frame = repository.save_frame(batch.batch_id, frame)
    repository.mark_processed(
        batch.batch_id,
        state="processed",
        processed_at=NOW + timedelta(seconds=2),
    )

    assert stored_observation == observation
    assert stored_frame == frame
    assert repository.observations_for_batch(batch.batch_id) == (observation,)
    assert repository.frame_for_batch(batch.batch_id) == frame
    assert repository.get_batch(batch.batch_id).processing_state == "processed"
    assert _count(session, NormalizedObservationRow) == 1
    assert _count(session, FusedFrameRow) == 1


def _heartbeat(**changes: object) -> DeviceHeartbeatRequest:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "device_id": "device_room_214",
        "stream_id": "boot-heartbeat",
        "sequence": 1,
        "device_monotonic_ms": 1000,
        "firmware_version": "bench-0.1.0",
        "buffered_packets": 0,
        "sources_seen": ["radar", "thermal", "wifi_csi"],
        "transport_status": "ok",
    }
    value.update(changes)
    return DeviceHeartbeatRequest.model_validate(value)


def test_heartbeat_retry_is_idempotent_and_conflict_is_rejected(
    session: Session,
) -> None:
    repository = HeartbeatRepository(session)
    first = repository.record("tenant_demo", _heartbeat(), received_at=NOW)
    second = repository.record(
        "tenant_demo",
        _heartbeat(),
        received_at=NOW + timedelta(seconds=1),
    )

    assert not first.duplicate
    assert second.duplicate
    assert second.received_at == NOW
    assert _count(session, DeviceHeartbeatIdentityRow) == 1

    with pytest.raises(ConcurrentUpdateError):
        repository.record(
            "tenant_demo",
            _heartbeat(buffered_packets=4),
            received_at=NOW + timedelta(seconds=2),
        )
