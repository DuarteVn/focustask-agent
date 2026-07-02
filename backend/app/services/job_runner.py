import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

JOB_TTL_MINUTES = 30
TTL_CHECK_INTERVAL_SECONDS = 300


@dataclass
class TelegramContext:
    chat_id: int
    message_id: int
    user_id: int


@dataclass
class ProcessingJob:
    job_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    error_message: Optional[str] = None
    task_id: Optional[str] = None
    telegram_ctx: Optional[TelegramContext] = None


_jobs: dict[str, ProcessingJob] = {}
_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_job() -> ProcessingJob:
    now = _now()
    job = ProcessingJob(
        job_id=str(uuid.uuid4()),
        status="received",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=JOB_TTL_MINUTES),
    )
    async with _lock:
        _jobs[job.job_id] = job
    logger.info("job_created job_id=%s", job.job_id)
    return job


async def get_job(job_id: str) -> Optional[ProcessingJob]:
    async with _lock:
        return _jobs.get(job_id)


async def _update_job(job_id: str, **kwargs) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = _now()


async def start_ttl_loop() -> None:
    logger.info("ttl_loop_started interval=%ds", TTL_CHECK_INTERVAL_SECONDS)
    while True:
        await asyncio.sleep(TTL_CHECK_INTERVAL_SECONDS)
        now = _now()
        async with _lock:
            expired = [
                jid for jid, j in _jobs.items()
                if j.status not in ("complete", "failed") and j.expires_at < now
            ]
            for jid in expired:
                _jobs[jid].status = "failed"
                _jobs[jid].error_message = "Processing timeout after 30 minutes"
                _jobs[jid].updated_at = now
                logger.warning("job_expired job_id=%s", jid)


async def run_job(job_id: str, temp_file_path: str) -> None:
    import os
    from concurrent.futures import ThreadPoolExecutor
    from app.services.whisper_service import WhisperService
    from app.services.gemini_service import GeminiService
    from app.db.repository import insert_task_record, TaskRecord
    from app.core.config import get_settings

    settings = get_settings()
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)

    try:
        # Duration check before transcribing
        await _check_duration(temp_file_path, settings.max_audio_duration_seconds, job_id)

        # Transcribe
        await _update_job(job_id, status="transcribing")
        logger.info("job_transcribing job_id=%s", job_id)
        whisper = WhisperService(settings)
        transcript, language = await loop.run_in_executor(
            executor, whisper.transcribe, temp_file_path
        )

        # Structure with LLM
        await _update_job(job_id, status="analyzing")
        logger.info("job_analyzing job_id=%s", job_id)
        gemini = GeminiService(settings)
        structured = await loop.run_in_executor(
            executor, gemini.structure, transcript, language
        )

        # Persist TaskRecord
        task_id = str(uuid.uuid4())
        duration = _get_duration(temp_file_path)
        record = TaskRecord(
            task_id=task_id,
            created_at=_now().isoformat().replace("+00:00", "Z"),
            audio_duration_seconds=duration,
            raw_transcript=transcript,
            detected_language=language,
            objective=structured["objective"],
            checklist=structured["checklist"],
            flow_input=structured["flow"]["input"],
            flow_logic=structured["flow"]["logic"],
            flow_output=structured["flow"]["output"],
        )
        await insert_task_record(record)
        await _update_job(job_id, status="complete", task_id=task_id)
        logger.info("job_complete job_id=%s task_id=%s", job_id, task_id)

    except Exception as exc:
        error_msg = str(exc)
        await _update_job(job_id, status="failed", error_message=error_msg)
        logger.error("job_failed job_id=%s error=%s", job_id, error_msg)
    finally:
        executor.shutdown(wait=False)
        try:
            os.remove(temp_file_path)
        except OSError:
            pass


_MD_V2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")


def _escape_md(text: str) -> str:
    return _MD_V2_SPECIAL.sub(r"\\\1", text)


def _format_telegram_message(record, web_panel_base_url: str) -> str:
    checklist = "\n".join(f"\\- {_escape_md(item)}" for item in record.checklist)
    url = f"{web_panel_base_url}/ui?task_id={record.task_id}"
    return (
        f"✅ *Pronto\\!*\n\n"
        f"🎯 *Objetivo*\n{_escape_md(record.objective)}\n\n"
        f"✅ *Checklist*\n{checklist}\n\n"
        f"⚙️ *Fluxo*\n"
        f"Input: {_escape_md(record.flow_input)}\n"
        f"Logic: {_escape_md(record.flow_logic)}\n"
        f"Output: {_escape_md(record.flow_output)}\n\n"
        f"[Ver no painel]({url})"
    )


async def run_job_telegram(job_id: str, file_path: str, ctx: TelegramContext) -> None:
    from app.core.config import get_settings
    from app.db.repository import get_task_record
    from app.telegram import bot as telegram_bot

    await _update_job(job_id, telegram_ctx=ctx)
    await run_job(job_id, file_path)

    job = await get_job(job_id)
    if job is None:
        logger.error("telegram_job_missing_after_run job_id=%s", job_id)
        return

    if telegram_bot.application is None:
        logger.error("telegram_bot_not_initialized job_id=%s", job_id)
        return

    if job.status == "complete":
        record = await get_task_record(job.task_id)
        settings = get_settings()
        text = _format_telegram_message(record, settings.web_panel_base_url)
        await telegram_bot.application.bot.send_message(
            chat_id=ctx.chat_id, text=text, parse_mode="MarkdownV2"
        )
    else:
        await telegram_bot.application.bot.send_message(
            chat_id=ctx.chat_id,
            text=f"❌ Falha ao processar áudio: {job.error_message}\nJob ID: {job_id}",
        )


async def _check_duration(file_path: str, max_seconds: int, job_id: str) -> None:
    duration = _get_duration(file_path)
    if duration and duration > max_seconds:
        raise ValueError(
            f"Audio duration {duration:.0f}s exceeds maximum of {max_seconds}s (45 minutes)"
        )


def _get_duration(file_path: str) -> Optional[float]:
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(file_path)
        if audio and audio.info:
            return audio.info.length
    except Exception:
        pass
    return None
