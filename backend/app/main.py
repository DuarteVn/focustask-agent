import asyncio
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, process, transcribe
from app.core.config import settings
from app.core.loop import set_main_loop
from app.db.database import close_db, init_db
from app.services.whisper_service import whisper_service
from app.telegram.bot import start_bot

# Suppress noisy third-party loggers
for _noisy in ("httpx", "telegram", "telegram.ext", "httpcore", "google_genai", "google_genai.models"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    set_main_loop(asyncio.get_running_loop())
    os.makedirs(settings.temp_audio_dir, exist_ok=True)
    await init_db()
    whisper_service.load()
    start_bot()

    _db = urlparse(settings.database_url)
    logger.info(
        "FocusTask iniciado | db=%s@%s | whisper=%s | llm=%s",
        _db.username or "?",
        _db.hostname or "?",
        settings.whisper_model,
        "gemini" if settings.gemini_api_key else "unconfigured",
    )

    yield

    await close_db()


app = FastAPI(
    title="FocusTask API",
    description="ADHD audio-to-structured-task pipeline",
    version="0.2.0",
    lifespan=lifespan,
)

# allow_credentials must stay False with wildcard origins (CORS spec forbids
# the combination); the API uses no cookies, so credentials are unnecessary.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(transcribe.router, prefix="/api")
app.include_router(process.router, prefix="/api")
