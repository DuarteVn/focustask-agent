import asyncio
import html
import logging
import os
import time

import httpx

from app.core.config import settings
from app.db.repository import create_job, set_done, set_error, set_processing  # noqa: F401
from app.services.gemini_service import gemini_service
from app.services.whisper_service import whisper_service

logger = logging.getLogger(__name__)


async def run_job(job_id: str, audio_bytes: bytes, filename: str = "audio.ogg") -> dict:
    """Transcribe + structure. Returns {objetivo, checklist, fluxo, transcript}."""
    t0 = time.perf_counter()
    try:
        logger.info("[%s] whisper start | size=%d bytes", job_id[:8], len(audio_bytes))
        result = await asyncio.to_thread(whisper_service.transcribe, audio_bytes, filename)
        transcript = result["raw_transcript"]
        language = result.get("language", "pt")
        t_whisper = time.perf_counter() - t0
        logger.info("[%s] whisper done | lang=%s | chars=%d | %.1fs", job_id[:8], language, len(transcript), t_whisper)

        await set_processing(job_id, transcript)

        structured = await asyncio.to_thread(gemini_service.structure, transcript, language)
        t_gemini = time.perf_counter() - t0 - t_whisper
        logger.info("[%s] gemini done | steps=%d | fluxo=%d | %.1fs", job_id[:8], len(structured.get("checklist", [])), len(structured.get("fluxo", [])), t_gemini)

        objetivo = structured.get("objetivo", "")
        checklist = structured.get("checklist", [])
        fluxo = structured.get("fluxo", [])

        await set_done(job_id, objetivo, checklist, fluxo)

        return {"objetivo": objetivo, "checklist": checklist, "fluxo": fluxo, "transcript": transcript}

    except Exception as e:
        logger.error("[%s] failed: %s", job_id[:8], e, exc_info=True)
        await set_error(job_id, str(e))
        raise


async def run_job_telegram(job_id: str, audio_bytes: bytes, chat_id: int) -> None:
    """Run pipeline and send Telegram reply via REST API (cross-loop safe)."""
    await create_job(job_id, source="telegram")
    t0 = time.perf_counter()
    try:
        result = await run_job(job_id, audio_bytes, "audio.ogg")
        msg = _format_result(result, job_id)
        await _send(chat_id, msg, parse_mode="HTML")
        logger.info("[%s] sent to chat=%s | total=%.1fs", job_id[:8], chat_id, time.perf_counter() - t0)
    except Exception as e:
        logger.error("[%s] telegram job error: %s", job_id[:8], e)
        await _send(chat_id, "❌ Erro ao processar o áudio. Tente novamente.")


async def _send(chat_id: int, text: str, parse_mode: str = "") -> None:
    payload: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
            timeout=30.0,
        )


def _format_result(result: dict, job_id: str) -> str:
    objetivo = html.escape(result.get("objetivo") or "—")
    checklist = result.get("checklist") or []
    fluxo = result.get("fluxo") or []

    lines = ["✅ <b>Pronto!</b>", "", "🎯 <b>Objetivo</b>", objetivo, "", "✅ <b>Checklist</b>"]

    for item in checklist:
        lines.append(f"• {html.escape(item)}")

    if fluxo:
        lines += ["", "⚙️ <b>Fluxo</b>"]
        for i, stage in enumerate(fluxo):
            escaped = html.escape(stage)
            if i == 0:
                lines.append(f"📥 {escaped}")
            elif i == len(fluxo) - 1:
                lines.append(f"✅ {escaped}")
            else:
                lines.append(f"• {escaped}")
            if i < len(fluxo) - 1:
                lines.append("↓")

    panel_url = f"{settings.web_panel_base_url}/jobs/{job_id}"
    lines += ["", f'<a href="{panel_url}">Ver no painel</a>']

    return "\n".join(lines)
