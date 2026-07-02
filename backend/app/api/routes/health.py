from fastapi import APIRouter
from app.core.config import get_settings
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    llm_status = "ready" if settings.gemini_api_key else "unconfigured"
    return HealthResponse(status="ok", whisper="ready", llm=llm_status)
