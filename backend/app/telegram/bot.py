import asyncio
import logging
import threading

from telegram.ext import Application, MessageHandler, filters

from app.core.config import settings
from app.telegram.handlers import handle_voice

logger = logging.getLogger(__name__)


def start_bot() -> None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")
        return
    thread = threading.Thread(target=_run_polling, daemon=True, name="telegram-bot")
    thread.start()
    logger.info("Telegram bot thread started")


def _run_polling() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    loop.run_until_complete(app.run_polling(drop_pending_updates=False))
