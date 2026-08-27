"""Mappings for durable monitoring status and calibration snapshots."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from backend.app.db.models import (
    CalibrationSnapshotRow,
    MonitoringSetupChangeRow,
    MonitoringStatusSnapshotRow,
)
from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationDimensionProgress,
    CalibrationProgress,
    SetupChangeAction,
)
from backend.app.domain.monitoring import (
    MonitoringReason,
    MonitoringSnapshot,
    MonitoringState,
    PresenceState,
)


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


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _stored_nonblank_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"stored {field} must be a nonblank string")
    return value.strip()


def _stored_counter(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"stored {field} must be a non-negative integer")
    return value


def _stored_unique_strings(
    value: object,
    field: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"stored {field} must be a list")
    normalized = tuple(
        _stored_nonblank_string(item, field)
        for item in value
    )
    if not allow_empty and not normalized:
        raise ValueError(f"stored {field} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"stored {field} must not contain duplicates")
    return normalized


def monitoring_to_row(
    tenant_id: str,
    stored: StoredMonitoringStatus,
) -> MonitoringStatusSnapshotRow:
    snapshot = stored.snapshot
    return MonitoringStatusSnapshotRow(
        tenant_id=tenant_id,
        resident_id=stored.resident_id,
        room_id=stored.room_id,
        observed_at=_utc(stored.observed_at),
        monitoring_state=snapshot.state.value,
        presence_state=snapshot.presence.value,
        baseline_learning_allowed=snapshot.baseline_learning_allowed,
        resident_measurements_allowed=snapshot.resident_measurements_allowed,
        reasons=[reason.value for reason in snapshot.reasons],
        quality_policy_version=snapshot.quality_policy_version,
        quality_policy_test_only=snapshot.quality_policy_test_only,
    )


def monitoring_from_row(row: MonitoringStatusSnapshotRow) -> StoredMonitoringStatus:
    if not isinstance(row.reasons, list) or not all(
        isinstance(reason, str) for reason in row.reasons
    ):
        raise ValueError("stored monitoring reasons must be a list of strings")
    return StoredMonitoringStatus(
        resident_id=row.resident_id,
        room_id=row.room_id,
        observed_at=_utc(row.observed_at),
        snapshot=MonitoringSnapshot(
            state=MonitoringState(row.monitoring_state),
            presence=PresenceState(row.presence_state),
            baseline_learning_allowed=row.baseline_learning_allowed,
            resident_measurements_allowed=row.resident_measurements_allowed,
            reasons=tuple(MonitoringReason(reason) for reason in row.reasons),
            quality_policy_version=row.quality_policy_version,
            quality_policy_test_only=row.quality_policy_test_only,
        ),
    )


def calibration_to_row(
    tenant_id: str,
    stored: StoredCalibration,
) -> CalibrationSnapshotRow:
    progress = stored.progress
    return CalibrationSnapshotRow(
        tenant_id=tenant_id,
        resident_id=stored.resident_id,
        version=stored.version,
        recorded_at=_utc(stored.recorded_at),
        setup_version=progress.setup_version,
        status=progress.status.value,
        eligible_windows=progress.eligible_windows,
        excluded_windows=progress.excluded_windows,
        reason=progress.reason,
        prior_setup_versions=list(progress.prior_setup_versions),
        dimension_progress=[
            {
                "dimension": dimension.dimension,
                "status": dimension.status.value,
                "eligible_windows": dimension.eligible_windows,
                "excluded_windows": dimension.excluded_windows,
            }
            for dimension in progress.dimension_progress
        ],
    )


def latest_setup_change_to_row(
    tenant_id: str,
    stored: StoredCalibration,
) -> MonitoringSetupChangeRow | None:
    if not stored.progress.setup_change_history:
        return None
    action = stored.progress.setup_change_history[-1]
    return MonitoringSetupChangeRow(
        tenant_id=tenant_id,
        resident_id=stored.resident_id,
        calibration_version=stored.version,
        previous_setup_version=action.previous_setup_version,
        new_setup_version=action.new_setup_version,
        affected_dimensions=list(action.affected_dimensions),
        reason=action.reason,
        actor_id=action.actor_id,
        changed_at=_utc(action.changed_at),
    )


def calibration_from_rows(
    row: CalibrationSnapshotRow,
    setup_rows: Iterable[MonitoringSetupChangeRow],
) -> StoredCalibration:
    prior_setup_versions = _stored_unique_strings(
        row.prior_setup_versions,
        "prior setup versions",
        allow_empty=True,
    )
    if not isinstance(row.dimension_progress, list):
        raise ValueError("stored dimension progress must be a list")

    dimensions: list[CalibrationDimensionProgress] = []
    seen_dimensions: set[str] = set()
    required_dimension_keys = {
        "dimension",
        "status",
        "eligible_windows",
        "excluded_windows",
    }
    for item in row.dimension_progress:
        if not isinstance(item, dict) or set(item) != required_dimension_keys:
            raise ValueError("stored dimension progress is malformed")
        dimension = _stored_nonblank_string(item["dimension"], "dimension")
        if dimension in seen_dimensions:
            raise ValueError("stored dimensions must not contain duplicates")
        seen_dimensions.add(dimension)
        status_value = _stored_nonblank_string(item["status"], "dimension status")
        dimensions.append(
            CalibrationDimensionProgress(
                dimension=dimension,
                status=BaselineStatus(status_value),
                eligible_windows=_stored_counter(
                    item["eligible_windows"],
                    "dimension eligible_windows",
                ),
                excluded_windows=_stored_counter(
                    item["excluded_windows"],
                    "dimension excluded_windows",
                ),
            )
        )

    actions: list[SetupChangeAction] = []
    for setup in setup_rows:
        actions.append(
            SetupChangeAction(
                previous_setup_version=setup.previous_setup_version,
                new_setup_version=setup.new_setup_version,
                affected_dimensions=_stored_unique_strings(
                    setup.affected_dimensions,
                    "affected dimensions",
                    allow_empty=False,
                ),
                reason=setup.reason,
                actor_id=setup.actor_id,
                changed_at=_utc(setup.changed_at),
            )
        )
    return StoredCalibration(
        resident_id=row.resident_id,
        version=row.version,
        recorded_at=_utc(row.recorded_at),
        progress=CalibrationProgress(
            setup_version=row.setup_version,
            status=BaselineStatus(row.status),
            eligible_windows=_stored_counter(
                row.eligible_windows,
                "eligible_windows",
            ),
            excluded_windows=_stored_counter(
                row.excluded_windows,
                "excluded_windows",
            ),
            reason=row.reason,
            prior_setup_versions=prior_setup_versions,
            dimension_progress=tuple(dimensions),
            setup_change_history=tuple(actions),
        ),
    )
