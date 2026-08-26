"""Small validation helpers shared by in-memory domain boundaries."""

from datetime import datetime
from enum import Enum
from math import isfinite
from numbers import Real
from typing import TypeVar


EnumValue = TypeVar("EnumValue", bound=Enum)


def require_nonblank_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string")
    return value.strip()


def require_aware_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be a timezone-aware datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


def coerce_enum(value: object, enum_type: type[EnumValue], field: str) -> EnumValue:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a valid {enum_type.__name__}") from exc


def require_strict_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")
    return value


def require_bounded_real(
    value: object,
    field: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a real number")
    normalized = float(value)
    if not isfinite(normalized) or not minimum <= normalized <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return normalized
