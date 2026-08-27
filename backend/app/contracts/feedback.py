from datetime import datetime
from typing import Literal

from backend.app.contracts.common import ContractModel


class MemoryEntryResponse(ContractModel):
    entry_id: str
    description: str
    source_feedback_id: str
    status: Literal["active", "retired"]
    created_by: str
    created_at: datetime
    retired_by: str | None
    retired_at: datetime | None
    retirement_reason: str | None


class ResidentMemoryResponse(ContractModel):
    resident_id: str
    version: int
    entries: list[MemoryEntryResponse]
