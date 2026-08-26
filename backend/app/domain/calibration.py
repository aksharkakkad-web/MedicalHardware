from dataclasses import dataclass, replace
from enum import StrEnum
from typing import ClassVar


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

    def __post_init__(self) -> None:
        if self.partial_eligible_windows < 1:
            raise ValueError("partial_eligible_windows must be positive")
        if self.established_eligible_windows <= self.partial_eligible_windows:
            raise ValueError("established threshold must exceed partial threshold")


@dataclass(frozen=True)
class CalibrationProgress:
    setup_version: str
    status: BaselineStatus
    eligible_windows: int
    excluded_windows: int
    reason: str
    prior_setup_versions: tuple[str, ...] = ()

    @classmethod
    def new(cls, setup_version: str) -> "CalibrationProgress":
        return cls(
            setup_version=setup_version,
            status=BaselineStatus.NEW,
            eligible_windows=0,
            excluded_windows=0,
            reason="initial_setup",
        )


def observe_calibration_window(
    progress: CalibrationProgress,
    *,
    policy: CalibrationPolicy,
    learning_allowed: bool,
    concerning: bool,
    unresolved_anomaly: bool,
) -> CalibrationProgress:
    eligible = learning_allowed and not concerning and not unresolved_anomaly
    eligible_windows = progress.eligible_windows + int(eligible)
    excluded_windows = progress.excluded_windows + int(not eligible)

    if eligible_windows >= policy.established_eligible_windows:
        status = BaselineStatus.ESTABLISHED
    elif eligible_windows >= policy.partial_eligible_windows:
        status = BaselineStatus.PARTIAL
    else:
        status = BaselineStatus.CALIBRATING

    return replace(
        progress,
        status=status,
        eligible_windows=eligible_windows,
        excluded_windows=excluded_windows,
    )


def start_recalibration(
    progress: CalibrationProgress,
    *,
    new_setup_version: str,
    reason: str,
) -> CalibrationProgress:
    if new_setup_version == progress.setup_version:
        raise ValueError("recalibration requires a new setup version")
    return CalibrationProgress(
        setup_version=new_setup_version,
        status=BaselineStatus.CALIBRATING,
        eligible_windows=0,
        excluded_windows=0,
        reason=reason,
        prior_setup_versions=progress.prior_setup_versions + (progress.setup_version,),
    )
