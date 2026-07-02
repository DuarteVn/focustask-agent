import asyncio
import logging
import uuid

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.loop import get_main_loop
from app.services.job_runner import run_job_telegram

logger = logging.getLogger(__name__)


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    voice = update.message.voice or update.message.audio
    if voice is None:
        return

    chat_id = update.effective_chat.id
    job_id = str(uuid.uuid4())

    # Download audio bytes directly (no temp file needed)
    tg_file = await ctx.bot.get_file(voice.file_id)
    audio_bytes = await tg_file.download_as_bytearray()

    logger.info("[%s] voice received | chat=%s | size=%s bytes", job_id[:8], chat_id, voice.file_size or "?")

    # ACK immediately (PTB runs fine in Telegram loop)
    await update.message.reply_text("⏳ Processando áudio…")

    # Schedule pipeline on FastAPI main loop — create_job happens there too
    asyncio.run_coroutine_threadsafe(
        run_job_telegram(job_id, bytes(audio_bytes), chat_id),
        get_main_loop(),
    )
