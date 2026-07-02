import logging

from telegram.ext import Application, ApplicationBuilder, MessageHandler, filters

from app.core.config import get_settings
from app.telegram.handlers import voice_or_audio_handler

logger = logging.getLogger(__name__)

application: Application | None = None


async def setup_bot() -> Application:
    global application
    settings = get_settings()
    application = ApplicationBuilder().token(settings.telegram_bot_token).build()
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, voice_or_audio_handler))

    if settings.telegram_webhook_url:
        await application.bot.set_webhook(settings.telegram_webhook_url)
        logger.info("telegram_webhook_set url=%s", settings.telegram_webhook_url)
    else:
        logger.info("telegram_polling_mode_configured")

    return application
