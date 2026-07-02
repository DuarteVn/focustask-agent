import asyncio
import logging
import os
import threading
import warnings
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import gradio as gr

from app.api.routes import health, jobs, tasks
from app.core.config import get_settings
from app.core.loop import set_main_loop
from app.db.database import close_db, init_db
from app.services.job_runner import start_ttl_loop
from app.telegram.bot import setup_bot
from app.ui.gradio_app import demo as gradio_demo

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# Silencia libs barulhentas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("gradio").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=UserWarning, module="gradio")


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_upload_bytes:
            return JSONResponse(
                status_code=413,
                content={"error": "File exceeds 500MB limit"},
            )
        return await call_next(request)


_telegram_application = None
_telegram_thread: threading.Thread | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _telegram_application, _telegram_thread
    set_main_loop(asyncio.get_running_loop())
    os.makedirs(settings.temp_audio_dir, exist_ok=True)
    await init_db()
    ttl_task = asyncio.create_task(start_ttl_loop())

    _db = urlparse(settings.database_url)
    logger.info("🚀 FocusTask iniciado | db=%s@%s", _db.username or "?", _db.hostname or "?")

    if settings.telegram_bot_token:
        _telegram_application = await setup_bot()
        if settings.telegram_webhook_url:
            await _telegram_application.initialize()
            await _telegram_application.start()
            logger.info("🤖 Telegram webhook ativo → %s", settings.telegram_webhook_url)
        else:
            _telegram_thread = threading.Thread(
                target=lambda: asyncio.run(_telegram_application.run_polling(stop_signals=None)),
                daemon=True,
            )
            _telegram_thread.start()
            logger.info("🤖 Telegram polling ativo")

    yield

    ttl_task.cancel()
    if _telegram_application is not None:
        if settings.telegram_webhook_url:
            await _telegram_application.stop()
            await _telegram_application.shutdown()
        else:
            _telegram_application.stop_running()
            if _telegram_thread is not None:
                _telegram_thread.join(timeout=5)
    await close_db()


app = FastAPI(title="FocusTask Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

app.include_router(health.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")

if settings.telegram_webhook_url:
    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request):
        from telegram import Update

        if _telegram_application is None:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")
        body = await request.json()
        update = Update.de_json(body, _telegram_application.bot)
        await _telegram_application.update_queue.put(update)
        return {"ok": True}

gr.mount_gradio_app(app, gradio_demo, path="/ui")
app.include_router(health.router)
app.include_router(transcribe.router)
app.include_router(process.router)
