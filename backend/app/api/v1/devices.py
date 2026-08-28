"""Tenant-safe clinic reads for devices and operational health."""

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import access_context, device_query_service
from backend.app.api.errors import READ_ERROR_RESPONSES
from backend.app.contracts.devices import DeviceHealthResponse, DeviceListResponse
from backend.app.services.device_queries import ProductDeviceQueryService
from backend.app.services.queries import AccessContext


router = APIRouter(prefix="/devices", tags=["devices"])


@router.get(
    "",
    response_model=DeviceListResponse,
    responses=READ_ERROR_RESPONSES,
)
def list_devices(
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductDeviceQueryService, Depends(device_query_service)],
) -> DeviceListResponse:
    return service.list_devices(context)


@router.get(
    "/{device_id}/health",
    response_model=DeviceHealthResponse,
    responses=READ_ERROR_RESPONSES,
)
def get_device_health(
    device_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductDeviceQueryService, Depends(device_query_service)],
) -> DeviceHealthResponse:
    return service.get_health(context, device_id)
