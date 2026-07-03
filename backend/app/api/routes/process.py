import asyncio
import logging
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import settings
from app.db.repository import create_job, set_done, set_processing, set_summary
from app.models.schemas import ProcessResponse, StructuredOutput
from app.services import audio_converter, job_runner
from app.services.gemini_service import PipelineStageError, gemini_service
from app.services.whisper_service import whisper_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["processing"])

# Fire-and-forget background jobs (async web flow, FR-023). Kept referenced so
# the event loop doesn't garbage-collect them mid-run.
_background_jobs: set[asyncio.Task] = set()


class TextInput(BaseModel):
    transcript: str


def _markdown_fields(job_id: str, structured: StructuredOutput) -> tuple[str, str]:
    from app.services import markdown_service

    md = markdown_service.render(structured.objetivo, structured.checklist, structured.fluxo)
    return md, f"/api/jobs/{job_id}/download.md"


async def _structure_and_persist(job_id: str, transcript: str, language: str = "pt") -> StructuredOutput:
    """Two-stage LLM path shared by both endpoints; persists summary + result."""
    try:
        summary = gemini_service.summarize(transcript, language)
        await set_summary(job_id, summary)
        structured = gemini_service.decompose(summary, language)
    except PipelineStageError as exc:
        raise HTTPException(
            status_code=500, detail=f"LLM processing failed: [{exc.stage}] {exc}"
        ) from exc

    validated = StructuredOutput(**structured)
    await set_done(job_id, validated.objetivo, validated.checklist, validated.fluxo)
    return validated


@router.post("/audio", response_model=None)
async def process_audio(file: UploadFile = File(...)):
    """Full pipeline: audio → Whisper → two-stage Gemini → structured JSON + Markdown.

    Long audio (> sync_processing_max_seconds) switches to async mode: 202 +
    job_id, pipeline runs in background, client polls GET /api/jobs/{job_id}.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    filename = file.filename or "audio.webm"
    try:
        duration = audio_converter.get_duration_seconds(audio_bytes, filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unreadable audio file: {exc}") from exc

    if duration > settings.max_audio_duration_seconds:
        raise HTTPException(status_code=400, detail="Áudio excede o limite de 45 minutos.")

    job_id = str(uuid.uuid4())
    await create_job(job_id, source="web")

    if duration > settings.sync_processing_max_seconds:
        task = asyncio.create_task(job_runner.run_job(job_id, audio_bytes, filename))
        _background_jobs.add(task)
        task.add_done_callback(_background_jobs.discard)
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": "pending",
                "status_url": f"/api/jobs/{job_id}",
            },
        )

    try:
        transcription = whisper_service.transcribe(audio_bytes, filename)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    transcript = transcription["raw_transcript"]
    await set_processing(job_id, transcript)

    structured = await _structure_and_persist(
        job_id, transcript, transcription.get("language", "pt")
    )
    markdown, markdown_url = _markdown_fields(job_id, structured)
    return ProcessResponse(
        job_id=job_id,
        raw_transcript=transcript,
        structured=structured,
        markdown=markdown,
        markdown_url=markdown_url,
    )


@router.post("/text", response_model=ProcessResponse)
async def process_text(body: TextInput) -> ProcessResponse:
    """Skip Whisper — two-stage Gemini directly on the transcript. Always sync."""
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="Empty transcript.")

    job_id = str(uuid.uuid4())
    await create_job(job_id, source="web")
    await set_processing(job_id, body.transcript)

    structured = await _structure_and_persist(job_id, body.transcript)
    markdown, markdown_url = _markdown_fields(job_id, structured)
    return ProcessResponse(
        job_id=job_id,
        raw_transcript=body.transcript,
        structured=structured,
        markdown=markdown,
        markdown_url=markdown_url,
    )
