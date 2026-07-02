import asyncio
import logging
import os
import uuid

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import get_settings
from app.core.loop import get_main_loop
from app.services.audio_converter import convert_to_wav
from app.services.job_runner import TelegramContext, create_job, run_job_telegram

logger = logging.getLogger(__name__)

_MAX_TELEGRAM_BYTES = 20 * 1024 * 1024
_CONVERT_EXTENSIONS = {".ogg", ".oga", ".opus"}


async def voice_or_audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    media = message.voice or message.audio
    if media is None:
        return

    if media.file_size and media.file_size > _MAX_TELEGRAM_BYTES:
        await message.reply_text("❌ Arquivo muito grande (max 20 MB)")
        return

    settings = get_settings()
    os.makedirs(settings.temp_audio_dir, exist_ok=True)

    tg_file = await context.bot.get_file(media.file_id)
    ext = os.path.splitext(tg_file.file_path or "")[1].lower() or ".oga"
    raw_path = os.path.join(settings.temp_audio_dir, f"{uuid.uuid4()}{ext}")
    await tg_file.download_to_drive(custom_path=raw_path)

    if ext in _CONVERT_EXTENSIONS:
        wav_path = os.path.splitext(raw_path)[0] + ".wav"
        convert_to_wav(raw_path, wav_path)
        os.remove(raw_path)
    else:
        wav_path = raw_path

    job = await create_job()
    ctx = TelegramContext(
        chat_id=message.chat_id,
        message_id=message.message_id,
        user_id=message.from_user.id if message.from_user else 0,
    )
    asyncio.run_coroutine_threadsafe(run_job_telegram(job.job_id, wav_path, ctx), get_main_loop())

    logger.info("telegram_upload_received job_id=%s chat_id=%s", job.job_id, message.chat_id)
    await message.reply_text(f"⏳ Processando seu áudio… Job ID: {job.job_id}")
