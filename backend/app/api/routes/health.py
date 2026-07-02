from fastapi import APIRouter
from app.core.config import get_settings
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    llm_status = "ready" if settings.gemini_api_key else "unconfigured"
    return HealthResponse(status="ok", whisper="ready", llm=llm_status)

from app.models.schemas import HealthResponse
from app.services.ollama_service import ollama_service
from app.services.whisper_service import whisper_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        whisper_loaded=whisper_service.is_loaded,
        ollama_reachable=await ollama_service.is_reachable(),
    )
