from typing import Literal

from backend.app.contracts.common import ContractModel, UTCDateTime


class MemoryEntryResponse(ContractModel):
    entry_id: str
    description: str
    source_feedback_id: str
    status: Literal["active", "retired"]
    created_by: str
    created_at: UTCDateTime
    retired_by: str | None
    retired_at: UTCDateTime | None
    retirement_reason: str | None


class ResidentMemoryResponse(ContractModel):
    resident_id: str
    version: int
    entries: list[MemoryEntryResponse]
