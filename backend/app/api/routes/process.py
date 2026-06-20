from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.models.schemas import ProcessResponse
from app.services.ollama_service import ollama_service
from app.services.whisper_service import whisper_service

router = APIRouter(prefix="/process", tags=["processing"])


class TextInput(BaseModel):
    transcript: str


@router.post("/audio", response_model=ProcessResponse)
async def process_audio(file: UploadFile = File(...)) -> ProcessResponse:
    """Full pipeline: audio → Whisper → Ollama → structured JSON."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        transcription = whisper_service.transcribe(
            audio_bytes, file.filename or "audio.webm"
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    try:
        structured = await ollama_service.process_transcript(
            transcription["raw_transcript"]
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {exc}") from exc

    return ProcessResponse(
        raw_transcript=transcription["raw_transcript"],
        structured=structured,
    )


@router.post("/text", response_model=ProcessResponse)
async def process_text(body: TextInput) -> ProcessResponse:
    """Skip Whisper — send transcript directly to Ollama. Useful for testing."""
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="Empty transcript.")

    try:
        structured = await ollama_service.process_transcript(body.transcript)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {exc}") from exc

    return ProcessResponse(raw_transcript=body.transcript, structured=structured)
