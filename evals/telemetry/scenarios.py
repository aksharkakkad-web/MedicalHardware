"""Deterministic production-envelope scenarios with truth kept out-of-band."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from backend.app.intelligence import FeaturePurpose


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = PROJECT_ROOT / "tests/fixtures/edge_telemetry/mahin_capture_v1.json"

REQUIRED_FAMILIES = frozenset(
    {
        "normal_variation",
        "away_return",
        "bathroom_like_absence",
        "unusual_movement",
        "inactivity",
        "physiological_deviation",
        "posture_fall_like",
        "source_ablation",
        "degraded_quality",
        "transport_replay",
        "assignment_failure",
        "recovery_recurrence",
    }
)


@dataclass(frozen=True)
class BaselineSpec:
    feature_name: str
    purpose: FeaturePurpose
    median: float
    mad: float
    iqr: float
    lower_quantile: float
    upper_quantile: float
    resolution_floor: float
    unit: str


@dataclass(frozen=True)
class TelemetryScenario:
    scenario_id: str
    family: str
    truth_label: str
    capture_payloads: tuple[list[dict[str, object]], ...]
    baseline: BaselineSpec | None = None
    presence: str = "resident_present"
    assignment_mode: str = "valid"
    expected_anomaly: bool = False
    expected_event: bool | None = None
    expected_duplicate: bool = False
    expected_conflict: bool = False
    expected_assignment_block: bool = False
    expected_features: tuple[str, ...] = ()
    expected_missing_sources: tuple[str, ...] = ()
    expected_sequence_gap: bool = False


MOVEMENT_BASELINE = BaselineSpec(
    "movement_energy",
    FeaturePurpose.MOVEMENT,
    0.2,
    0.03,
    0.08,
    0.08,
    0.32,
    0.05,
    "normalized",
)
INACTIVITY_BASELINE = BaselineSpec(
    "movement_energy",
    FeaturePurpose.MOVEMENT,
    0.8,
    0.04,
    0.1,
    0.65,
    0.95,
    0.05,
    "normalized",
)
HEART_BASELINE = BaselineSpec(
    "heart_rate",
    FeaturePurpose.PHYSIOLOGY,
    72.0,
    2.0,
    5.0,
    66.0,
    78.0,
    1.0,
    "bpm",
)
HEIGHT_BASELINE = BaselineSpec(
    "tracked_height",
    FeaturePurpose.POSTURE,
    1.6,
    0.05,
    0.1,
    1.45,
    1.75,
    0.05,
    "m",
)


def _capture(
    scenario_id: str,
    sequence: int,
    *,
    sources: tuple[str, ...] = ("radar", "thermal", "wifi_csi"),
    stream_id: str | None = None,
    movement: float | None = None,
    heart_rate: float | None = None,
    tracked_height: float | None = None,
    low_quality: bool = False,
    room_id: str = "room_214",
) -> list[dict[str, object]]:
    capture: list[dict[str, object]] = []
    for original in json.loads(FIXTURE.read_text()):
        if original["source"] not in sources:
            continue
        item = deepcopy(original)
        item["room_id"] = room_id
        item["stream_id"] = stream_id or f"eval-{scenario_id}"
        item["sequence"] = sequence
        item["transport"] = {
            "batch_id": f"{scenario_id}-{sequence}-{item['source']}",
            "retry_count": 0,
        }
        payload = item["payload"]
        if movement is not None and item["source"] in {"radar", "wifi_csi"}:
            payload["movement_score"] = movement
        if heart_rate is not None and item["source"] == "radar":
            payload["heart_rate_bpm"] = heart_rate
        if tracked_height is not None and item["source"] in {"radar", "thermal"}:
            payload["tracked_height_m"] = tracked_height
            payload["position_state"] = (
                "floor_like" if tracked_height < 0.7 else "upright_like"
            )
            payload["vertical_velocity_mps"] = -0.8
        if low_quality:
            payload["signal_quality"] = 0.2
            item["quality_reasons"] = ["low signal quality"]
        capture.append(item)
    return capture


def _three(
    scenario_id: str,
    *,
    movement: float | None = None,
    heart_rate: float | None = None,
    tracked_height: float | None = None,
) -> tuple[list[dict[str, object]], ...]:
    return tuple(
        _capture(
            scenario_id,
            sequence,
            movement=movement,
            heart_rate=heart_rate,
            tracked_height=tracked_height,
        )
        for sequence in (1, 2, 3)
    )


def scenarios() -> tuple[TelemetryScenario, ...]:
    suite: list[TelemetryScenario] = []

    for index, movement in enumerate((0.12, 0.16, 0.19, 0.22, 0.26, 0.3), start=1):
        scenario_id = f"normal_variation_{index:02d}"
        suite.append(
            TelemetryScenario(
                scenario_id,
                "normal_variation",
                f"ordinary_variation_{index}",
                _three(scenario_id, movement=movement),
                baseline=MOVEMENT_BASELINE,
                expected_event=False,
                expected_features=("movement_energy", "heart_rate"),
            )
        )

    for family, count in (("away_return", 4), ("bathroom_like_absence", 4)):
        for index in range(1, count + 1):
            scenario_id = f"{family}_{index:02d}"
            suite.append(
                TelemetryScenario(
                    scenario_id,
                    family,
                    f"resident_away_context_{index}",
                    _three(scenario_id, movement=0.95),
                    baseline=MOVEMENT_BASELINE,
                    presence="resident_away",
                    expected_event=False,
                    expected_features=("movement_energy",),
                )
            )

    for index in range(1, 7):
        scenario_id = f"unusual_movement_{index:02d}"
        suite.append(
            TelemetryScenario(
                scenario_id,
                "unusual_movement",
                f"persistent_movement_deviation_{index}",
                _three(scenario_id, movement=0.9 + index / 100),
                baseline=MOVEMENT_BASELINE,
                expected_anomaly=True,
                expected_features=("movement_energy",),
            )
        )

    for index in range(1, 5):
        scenario_id = f"inactivity_{index:02d}"
        suite.append(
            TelemetryScenario(
                scenario_id,
                "inactivity",
                f"sustained_low_movement_{index}",
                _three(scenario_id, movement=0.01 * index),
                baseline=INACTIVITY_BASELINE,
                expected_anomaly=True,
                expected_features=("movement_energy",),
            )
        )

    for index in range(1, 5):
        scenario_id = f"physiological_deviation_{index:02d}"
        suite.append(
            TelemetryScenario(
                scenario_id,
                "physiological_deviation",
                f"heart_rate_deviation_{index}",
                _three(scenario_id, heart_rate=112.0 + index),
                baseline=HEART_BASELINE,
                expected_anomaly=True,
                expected_features=("heart_rate", "respiratory_rate"),
            )
        )

    for index in range(1, 5):
        scenario_id = f"posture_fall_like_{index:02d}"
        suite.append(
            TelemetryScenario(
                scenario_id,
                "posture_fall_like",
                f"low_height_posture_evidence_{index}",
                _three(scenario_id, tracked_height=0.25 + index / 100),
                baseline=HEIGHT_BASELINE,
                expected_anomaly=True,
                expected_features=("tracked_height", "position_state"),
            )
        )

    ablations = (
        ("radar", ("thermal", "wifi_csi")),
        ("thermal", ("radar", "wifi_csi")),
        ("wifi_csi", ("radar", "thermal")),
        ("thermal+wifi_csi", ("radar",)),
    )
    for index, (missing_label, present) in enumerate(ablations, start=1):
        scenario_id = f"source_ablation_{index:02d}"
        suite.append(
            TelemetryScenario(
                scenario_id,
                "source_ablation",
                f"missing_{missing_label}",
                (_capture(scenario_id, 1, sources=present),),
                expected_features=(
                    ("heart_rate",) if "radar" in present else ("person_detected",)
                ),
                expected_missing_sources=tuple(
                    sorted(set(("radar", "thermal", "wifi_csi")) - set(present))
                ),
            )
        )

    for index in range(1, 5):
        scenario_id = f"degraded_quality_{index:02d}"
        suite.append(
            TelemetryScenario(
                scenario_id,
                "degraded_quality",
                f"low_signal_capture_{index}",
                (_capture(scenario_id, 1, low_quality=True),),
                expected_features=("signal_health", "movement_energy"),
            )
        )

    retry_id = "transport_replay_01"
    retry = _capture(retry_id, 1)
    suite.append(
        TelemetryScenario(
            retry_id,
            "transport_replay",
            "exact_network_retry",
            (retry, deepcopy(retry)),
            expected_duplicate=True,
            expected_features=("heart_rate",),
        )
    )
    conflict_id = "transport_replay_02"
    original = _capture(conflict_id, 1)
    changed = deepcopy(original)
    changed[0]["payload"]["heart_rate_bpm"] = 99.0
    suite.append(
        TelemetryScenario(
            conflict_id,
            "transport_replay",
            "changed_identity_conflict",
            (original, changed),
            expected_conflict=True,
            expected_features=("heart_rate",),
        )
    )
    stale_id = "transport_replay_03"
    suite.append(
        TelemetryScenario(
            stale_id,
            "transport_replay",
            "same_stream_stale_packet",
            (_capture(stale_id, 2), _capture(stale_id, 1)),
            expected_conflict=True,
            expected_features=("heart_rate",),
        )
    )
    stream_id = "transport_replay_04"
    suite.append(
        TelemetryScenario(
            stream_id,
            "transport_replay",
            "gap_then_new_stream_restart",
            (
                _capture(stream_id, 1, stream_id="boot-a"),
                _capture(stream_id, 4, stream_id="boot-a"),
                _capture(stream_id, 1, stream_id="boot-b"),
            ),
            expected_sequence_gap=True,
            expected_features=("heart_rate",),
        )
    )

    missing_id = "assignment_failure_01"
    suite.append(
        TelemetryScenario(
            missing_id,
            "assignment_failure",
            "device_assignment_missing",
            (_capture(missing_id, 1),),
            assignment_mode="missing",
            expected_assignment_block=True,
        )
    )
    mismatch_id = "assignment_failure_02"
    suite.append(
        TelemetryScenario(
            mismatch_id,
            "assignment_failure",
            "declared_room_mismatch",
            (_capture(mismatch_id, 1, room_id="room_spare"),),
            assignment_mode="mismatch",
            expected_assignment_block=True,
        )
    )

    for index in range(1, 3):
        scenario_id = f"recovery_recurrence_{index:02d}"
        captures = (
            *_three(scenario_id, movement=0.95),
            *tuple(
                _capture(scenario_id, sequence, movement=0.2)
                for sequence in (4, 5, 6)
            ),
            *tuple(
                _capture(scenario_id, sequence, movement=0.95)
                for sequence in (7, 8, 9)
            ),
        )
        suite.append(
            TelemetryScenario(
                scenario_id,
                "recovery_recurrence",
                f"recovered_then_recurred_{index}",
                captures,
                baseline=MOVEMENT_BASELINE,
                expected_anomaly=True,
                expected_features=("movement_energy",),
            )
        )

    if len(suite) != 48:
        raise RuntimeError(f"telemetry suite must contain 48 cases, got {len(suite)}")
    return tuple(suite)


__all__ = [
    "BaselineSpec",
    "REQUIRED_FAMILIES",
    "TelemetryScenario",
    "scenarios",
]
