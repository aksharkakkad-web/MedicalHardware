from typing import Literal

from backend.app.contracts.common import ContractModel


class ResidentSummary(ContractModel):
    resident_id: str
    display_label: str
    room_id: str
    room_label: str
    assignment_status: Literal["active"]


class ResidentListResponse(ContractModel):
    items: list[ResidentSummary]
