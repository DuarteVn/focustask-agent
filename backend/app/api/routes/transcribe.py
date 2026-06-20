from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import TranscriptionResponse
from app.services.whisper_service import whisper_service

router = APIRouter(prefix="/transcribe", tags=["transcription"])


@router.post("/", response_model=TranscriptionResponse)
async def transcribe_audio(file: UploadFile = File(...)) -> TranscriptionResponse:
    """Receive audio file, return raw transcript."""
    allowed = {
        "audio/webm", "audio/ogg", "audio/wav", "audio/mpeg",
        "audio/mp4", "audio/x-m4a", "application/octet-stream",
    }
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {file.content_type}",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    try:
        result = whisper_service.transcribe(audio_bytes, file.filename or "audio.webm")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return TranscriptionResponse(**result)
