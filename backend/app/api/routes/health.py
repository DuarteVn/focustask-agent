from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse
from app.services.whisper_service import whisper_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        whisper_loaded=whisper_service.is_loaded,
        llm="ready" if settings.gemini_api_key else "unconfigured",
    )
