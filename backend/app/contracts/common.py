from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict


def _require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("datetime must use UTC")
    return value


UTCDateTime = Annotated[AwareDatetime, AfterValidator(_require_utc)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class HealthResponse(ContractModel):
    status: Literal["ready"]
    service: Literal["product-api"]


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    field: str | None = None


class ErrorEnvelope(ContractModel):
    error: ErrorDetail
