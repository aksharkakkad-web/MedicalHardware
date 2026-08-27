from fastapi import APIRouter

from backend.app.api.v1 import events, residents


router = APIRouter(prefix="/v1")
router.include_router(residents.router)
router.include_router(events.router)
