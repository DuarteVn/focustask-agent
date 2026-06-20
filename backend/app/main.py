import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, process, transcribe
from app.core.config import settings
from app.services.ollama_service import ollama_service
from app.services.whisper_service import whisper_service

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    Path(settings.temp_audio_dir).mkdir(parents=True, exist_ok=True)
    whisper_service.load()
    yield
    # Shutdown
    await ollama_service.aclose()


app = FastAPI(
    title="TDAH Task API",
    description="Local AI pipeline: audio → transcript → ADHD-structured tasks",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(transcribe.router)
app.include_router(process.router)
