import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.db.repository import create_job
from app.models.schemas import ProcessResponse, StructuredOutput
from app.services.gemini_service import gemini_service
from app.services.whisper_service import whisper_service

router = APIRouter(prefix="/process", tags=["processing"])


class TextInput(BaseModel):
    transcript: str


@router.post("/audio", response_model=ProcessResponse)
async def process_audio(file: UploadFile = File(...)) -> ProcessResponse:
    """Full pipeline: audio → Whisper → Gemini → structured JSON."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    job_id = str(uuid.uuid4())
    await create_job(job_id, source="web")

    try:
        transcription = whisper_service.transcribe(audio_bytes, file.filename or "audio.webm")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    try:
        structured = gemini_service.structure(
            transcription["raw_transcript"], transcription.get("language", "pt")
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {exc}") from exc

    return ProcessResponse(
        job_id=job_id,
        raw_transcript=transcription["raw_transcript"],
        structured=StructuredOutput(**structured),
    )


@router.post("/text", response_model=ProcessResponse)
async def process_text(body: TextInput) -> ProcessResponse:
    """Skip Whisper — send transcript directly to Gemini."""
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="Empty transcript.")

    job_id = str(uuid.uuid4())
    await create_job(job_id, source="web")

    try:
        structured = gemini_service.structure(body.transcript)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {exc}") from exc

    return ProcessResponse(
        job_id=job_id,
        raw_transcript=body.transcript,
        structured=StructuredOutput(**structured),
    )
