from core import settings
from fastapi import APIRouter

router = APIRouter(prefix=settings.api_prefix.healthcheck, tags=["Healthcheck"])


@router.get("")
async def healthcheck():
    return {
        "message": "success",
    }
