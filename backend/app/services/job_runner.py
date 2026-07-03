import asyncio
import html
import logging
import time

import httpx

from app.core.config import settings
from app.db.repository import create_job, set_done, set_error, set_processing, set_summary  # noqa: F401
from app.services.gemini_service import PipelineStageError, gemini_service
from app.services.whisper_service import whisper_service

logger = logging.getLogger(__name__)

_TIMEOUT_POLL_SECONDS = 5.0


async def run_job(job_id: str, audio_bytes: bytes, filename: str = "audio.ogg", progress: dict | None = None) -> dict:
    """Transcribe + two-stage structure. Returns {objetivo, checklist, fluxo, transcript}."""
    t0 = time.perf_counter()
    try:
        logger.info("[%s] whisper start | size=%d bytes", job_id[:8], len(audio_bytes))

        def _on_progress(pct: int) -> None:
            logger.info("[%s] whisper progress | %d%%", job_id[:8], pct)
            if progress is not None:
                progress["stage"] = "transcrevendo"
                progress["pct"] = pct

        result = await asyncio.to_thread(whisper_service.transcribe, audio_bytes, filename, _on_progress)
        transcript = result["raw_transcript"]
        language = result.get("language", "pt")
        t_whisper = time.perf_counter() - t0
        logger.info("[%s] whisper done | lang=%s | chars=%d | %.1fs", job_id[:8], language, len(transcript), t_whisper)

        if progress is not None:
            progress["duration_seconds"] = result.get("duration_seconds", 0)

        await set_processing(job_id, transcript)

        if progress is not None:
            progress["stage"] = "sumarizando"
            progress["pct"] = 0

        summary = await asyncio.to_thread(gemini_service.summarize, transcript, language)
        await set_summary(job_id, summary)
        t_stage1 = time.perf_counter() - t0 - t_whisper
        logger.info("[%s] summarize done | chars=%d | %.1fs", job_id[:8], len(summary), t_stage1)

        if progress is not None:
            progress["stage"] = "estruturando"
            progress["pct"] = 0

        structured = await asyncio.to_thread(gemini_service.decompose, summary, language)
        t_stage2 = time.perf_counter() - t0 - t_whisper - t_stage1
        logger.info("[%s] decompose done | steps=%d | fluxo=%d | %.1fs", job_id[:8], len(structured.get("checklist", [])), len(structured.get("fluxo", [])), t_stage2)

        objetivo = structured.get("objetivo", "")
        checklist = structured.get("checklist", [])
        fluxo = structured.get("fluxo", [])

        await set_done(job_id, objetivo, checklist, fluxo)

        return {"objetivo": objetivo, "checklist": checklist, "fluxo": fluxo, "transcript": transcript}

    except PipelineStageError as e:
        logger.error("[%s] failed at stage=%s: %s", job_id[:8], e.stage, e, exc_info=True)
        await set_error(job_id, f"[{e.stage}] {e}")
        raise
    except Exception as e:
        logger.error("[%s] failed: %s", job_id[:8], e, exc_info=True)
        await set_error(job_id, str(e))
        raise


async def run_job_telegram(job_id: str, audio_bytes: bytes, chat_id: int) -> None:
    """Run pipeline and send Telegram reply via REST API (cross-loop safe)."""
    await create_job(job_id, source="telegram")
    t0 = time.perf_counter()
    progress: dict = {"stage": "transcrevendo", "pct": 0}
    heartbeat = asyncio.create_task(_heartbeat(job_id, chat_id, progress))
    task = asyncio.create_task(run_job(job_id, audio_bytes, "audio.ogg", progress))
    try:
        result = await _wait_with_dynamic_timeout(task, progress, t0)
        msg = _format_result(result, job_id)
        await _send(chat_id, msg, parse_mode="HTML")
        logger.info("[%s] sent to chat=%s | total=%.1fs", job_id[:8], chat_id, time.perf_counter() - t0)
    except asyncio.TimeoutError:
        logger.error("[%s] telegram job timed out after %.1fs", job_id[:8], time.perf_counter() - t0)
        await set_error(job_id, f"timeout after {time.perf_counter() - t0:.0f}s")
        await _send(chat_id, "❌ O processamento demorou demais e foi cancelado. Tente um áudio mais curto.")
    except Exception as e:
        logger.error("[%s] telegram job error: %s", job_id[:8], e)
        await _send(chat_id, "❌ Erro ao processar o áudio. Tente novamente.")
    finally:
        heartbeat.cancel()


async def _wait_with_dynamic_timeout(task: asyncio.Task, progress: dict, t0: float) -> dict:
    """Timeout scales with measured audio duration (research R4).

    Base timeout applies until Whisper reports duration; afterwards the
    effective limit is max(base, duration * job_timeout_factor) so a 45-min
    audio gets ~68 min while a stuck 30-second job still dies at the base.
    """
    while True:
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=_TIMEOUT_POLL_SECONDS)
        except asyncio.TimeoutError:
            base = settings.job_timeout_seconds
            duration = progress.get("duration_seconds") or 0
            effective = max(base, duration * settings.job_timeout_factor) if duration else base
            if time.perf_counter() - t0 >= effective:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise


async def _heartbeat(job_id: str, chat_id: int, progress: dict) -> None:
    """Notify the user the job is still alive on long-running audio, with % when known."""
    delay = settings.job_heartbeat_seconds
    try:
        while True:
            await asyncio.sleep(delay)
            stage = progress.get("stage", "processando")
            pct = progress.get("pct", 0)
            logger.info("[%s] still %s | %d%%", job_id[:8], stage, pct)
            if stage == "transcrevendo" and pct:
                text = f"⏳ Transcrevendo... {pct}% concluído (áudio longo)."
            elif stage == "sumarizando":
                text = "⏳ Transcrição concluída, consolidando o contexto..."
            elif stage == "estruturando":
                text = "⏳ Contexto consolidado, estruturando tarefas..."
            else:
                text = "⏳ Ainda processando... áudio longo pode levar alguns minutos."
            await _send(chat_id, text)
            delay = min(delay * 2, 120)
    except asyncio.CancelledError:
        pass


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
    download_url = f"{settings.web_panel_base_url}/jobs/{job_id}/download.md"
    lines += ["", f'<a href="{panel_url}">Ver no painel</a>', f'<a href="{download_url}">Baixar Markdown (Obsidian)</a>']

    return "\n".join(lines)
