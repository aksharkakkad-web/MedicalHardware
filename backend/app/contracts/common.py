from typing import Literal

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class HealthResponse(ContractModel):
    status: Literal["ready"]
    service: Literal["product-api"]


class ErrorDetail(ContractModel):
    code: str
    message: str
    field: str | None = None


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorDetail
