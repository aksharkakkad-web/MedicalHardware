from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import ClassVar

from backend.app.domain._validation import (
    require_aware_datetime,
    require_nonblank_text,
    require_strict_bool,
)
from backend.app.domain.monitoring import MonitoringSnapshot


class BaselineStatus(StrEnum):
    NEW = "new"
    CALIBRATING = "calibrating"
    PARTIAL = "partial"
    ESTABLISHED = "established"


@dataclass(frozen=True)
class CalibrationPolicy:
    """Synthetic/test-only calibration thresholds for the toy scenario."""

    SYNTHETIC_TEST_ONLY: ClassVar[bool] = True
    partial_eligible_windows: int
    established_eligible_windows: int
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.partial_eligible_windows < 1:
            raise ValueError("partial_eligible_windows must be positive")
        if self.established_eligible_windows <= self.partial_eligible_windows:
            raise ValueError("established threshold must exceed partial threshold")


@dataclass(frozen=True)
class CalibrationDimensionProgress:
    dimension: str
    status: BaselineStatus
    eligible_windows: int = 0
    excluded_windows: int = 0
    schema_version: str = "1.0"


@dataclass(frozen=True)
class SetupChangeAction:
    previous_setup_version: str
    new_setup_version: str
    affected_dimensions: tuple[str, ...]
    reason: str
    actor_id: str
    changed_at: datetime
    schema_version: str = "1.0"


@dataclass(frozen=True)
class CalibrationProgress:
    setup_version: str
    status: BaselineStatus
    eligible_windows: int
    excluded_windows: int
    reason: str
    prior_setup_versions: tuple[str, ...] = ()
    dimension_progress: tuple[CalibrationDimensionProgress, ...] = ()
    setup_change_history: tuple[SetupChangeAction, ...] = ()
    schema_version: str = "1.0"

    @classmethod
    def new(
        cls,
        setup_version: str,
        *,
        dimensions: tuple[str, ...] = (),
    ) -> "CalibrationProgress":
        setup_version = require_nonblank_text(setup_version, "setup_version")
        dimensions = _normalize_dimensions(dimensions, allow_empty=True)
        return cls(
            setup_version=setup_version,
            status=BaselineStatus.NEW,
            eligible_windows=0,
            excluded_windows=0,
            reason="initial_setup",
            dimension_progress=tuple(
                CalibrationDimensionProgress(
                    dimension=dimension,
                    status=BaselineStatus.NEW,
                )
                for dimension in dimensions
            ),
        )

    def dimension(self, dimension: str) -> CalibrationDimensionProgress:
        dimension = require_nonblank_text(dimension, "dimension")
        for progress in self.dimension_progress:
            if progress.dimension == dimension:
                return progress
        raise KeyError(f"Unknown calibration dimension: {dimension}")


def _normalize_dimensions(
    dimensions: tuple[str, ...],
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(dimensions, tuple):
        raise ValueError("dimensions must be a tuple")
    normalized = tuple(
        require_nonblank_text(dimension, "dimension")
        for dimension in dimensions
    )
    if not allow_empty and not normalized:
        raise ValueError("affected_dimensions must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError("dimensions must not contain duplicates")
    return normalized


def _status_for_windows(
    eligible_windows: int,
    policy: CalibrationPolicy,
) -> BaselineStatus:
    if eligible_windows >= policy.established_eligible_windows:
        return BaselineStatus.ESTABLISHED
    if eligible_windows >= policy.partial_eligible_windows:
        return BaselineStatus.PARTIAL
    return BaselineStatus.CALIBRATING


def _aggregate_dimension_status(
    dimensions: tuple[CalibrationDimensionProgress, ...],
) -> BaselineStatus:
    if all(
        dimension.status == BaselineStatus.ESTABLISHED
        for dimension in dimensions
    ):
        return BaselineStatus.ESTABLISHED
    if any(
        dimension.status in (BaselineStatus.PARTIAL, BaselineStatus.ESTABLISHED)
        for dimension in dimensions
    ):
        return BaselineStatus.PARTIAL
    return BaselineStatus.CALIBRATING


def observe_calibration_window(
    progress: CalibrationProgress,
    *,
    policy: CalibrationPolicy,
    learning_allowed: bool | None = None,
    monitoring_snapshot: MonitoringSnapshot | None = None,
    concerning: bool,
    unresolved_anomaly: bool,
) -> CalibrationProgress:
    if monitoring_snapshot is not None:
        if not isinstance(monitoring_snapshot, MonitoringSnapshot):
            raise ValueError("monitoring_snapshot must be a MonitoringSnapshot")
        snapshot_allows_learning = monitoring_snapshot.baseline_learning_allowed
        if learning_allowed is not None:
            learning_allowed = require_strict_bool(
                learning_allowed,
                "learning_allowed",
            )
            if learning_allowed != snapshot_allows_learning:
                raise ValueError(
                    "learning_allowed contradicts monitoring_snapshot"
                )
        learning_allowed = snapshot_allows_learning
    elif learning_allowed is None:
        raise ValueError("learning eligibility requires monitoring_snapshot or boolean")
    else:
        learning_allowed = require_strict_bool(
            learning_allowed,
            "learning_allowed",
        )
    concerning = require_strict_bool(concerning, "concerning")
    unresolved_anomaly = require_strict_bool(
        unresolved_anomaly,
        "unresolved_anomaly",
    )
    eligible = learning_allowed and not concerning and not unresolved_anomaly
    eligible_windows = progress.eligible_windows + int(eligible)
    excluded_windows = progress.excluded_windows + int(not eligible)

    if progress.dimension_progress:
        dimensions = tuple(
            replace(
                dimension,
                status=_status_for_windows(
                    dimension.eligible_windows + int(eligible),
                    policy,
                ),
                eligible_windows=dimension.eligible_windows + int(eligible),
                excluded_windows=dimension.excluded_windows + int(not eligible),
            )
            for dimension in progress.dimension_progress
        )
        status = _aggregate_dimension_status(dimensions)
    else:
        dimensions = ()
        status = _status_for_windows(eligible_windows, policy)

    return replace(
        progress,
        status=status,
        eligible_windows=eligible_windows,
        excluded_windows=excluded_windows,
        dimension_progress=dimensions,
    )


def start_recalibration(
    progress: CalibrationProgress,
    *,
    new_setup_version: str,
    reason: str,
    actor_id: str,
    changed_at: datetime,
    affected_dimensions: tuple[str, ...] | None = None,
) -> CalibrationProgress:
    new_setup_version = require_nonblank_text(
        new_setup_version,
        "new_setup_version",
    )
    reason = require_nonblank_text(reason, "reason")
    actor_id = require_nonblank_text(actor_id, "actor_id")
    changed_at = require_aware_datetime(changed_at, "changed_at")
    if new_setup_version == progress.setup_version:
        raise ValueError("recalibration requires a new setup version")

    if progress.setup_change_history:
        previous_change_at = progress.setup_change_history[-1].changed_at
        if changed_at < previous_change_at:
            raise ValueError("changed_at cannot precede setup-change history")

    if progress.dimension_progress:
        configured_dimensions = tuple(
            dimension.dimension for dimension in progress.dimension_progress
        )
        if affected_dimensions is None:
            affected = configured_dimensions
        else:
            affected = _normalize_dimensions(
                affected_dimensions,
                allow_empty=False,
            )
        unknown = set(affected) - set(configured_dimensions)
        if unknown:
            raise ValueError(
                "affected_dimensions must reference configured dimensions"
            )
        dimensions = tuple(
            replace(
                dimension,
                status=BaselineStatus.CALIBRATING,
                eligible_windows=0,
                excluded_windows=0,
            )
            if dimension.dimension in affected
            else dimension
            for dimension in progress.dimension_progress
        )
        status = _aggregate_dimension_status(dimensions)
        all_dimensions_affected = set(affected) == set(configured_dimensions)
        eligible_windows = 0 if all_dimensions_affected else progress.eligible_windows
        excluded_windows = 0 if all_dimensions_affected else progress.excluded_windows
    else:
        if affected_dimensions is not None:
            _normalize_dimensions(affected_dimensions, allow_empty=False)
            raise ValueError(
                "affected_dimensions require configured dimension progress"
            )
        affected = ("all_physical_dimensions",)
        dimensions = ()
        status = BaselineStatus.CALIBRATING
        eligible_windows = 0
        excluded_windows = 0

    action = SetupChangeAction(
        previous_setup_version=progress.setup_version,
        new_setup_version=new_setup_version,
        affected_dimensions=affected,
        reason=reason,
        actor_id=actor_id,
        changed_at=changed_at,
    )
    return CalibrationProgress(
        setup_version=new_setup_version,
        status=status,
        eligible_windows=eligible_windows,
        excluded_windows=excluded_windows,
        reason=reason,
        prior_setup_versions=progress.prior_setup_versions + (progress.setup_version,),
        dimension_progress=dimensions,
        setup_change_history=progress.setup_change_history + (action,),
    )
