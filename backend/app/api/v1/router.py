from fastapi import APIRouter

from backend.app.api.v1 import devices, events, resident_status, residents


router = APIRouter(prefix="/v1")
router.include_router(residents.router)
router.include_router(resident_status.router)
router.include_router(events.router)
router.include_router(devices.router)
