from fastapi import APIRouter
from public.controllers.sms_controller import router as sms_router

router = APIRouter()
router.include_router(sms_router, prefix="/api/sms", tags=["sms"]) 