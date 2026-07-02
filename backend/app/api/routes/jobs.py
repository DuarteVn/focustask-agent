import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.models.schemas import JobCreatedResponse, JobStatusResponse
from app.services.job_runner import create_job, get_job, run_job

logger = logging.getLogger(__name__)
router = APIRouter()

_ACCEPTED_TYPES = {
    "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4",
    "audio/webm", "video/webm", "audio/x-wav", "audio/wave",
    "audio/mp3", "audio/x-m4a",
}
_ACCEPTED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".webm"}


def _is_accepted(content_type: str, filename: str) -> bool:
    if content_type and content_type.split(";")[0].strip().lower() in _ACCEPTED_TYPES:
        return True
    ext = os.path.splitext(filename or "")[1].lower()
    return ext in _ACCEPTED_EXTENSIONS


@router.post("/jobs", status_code=202, response_model=JobCreatedResponse)
async def upload_audio(file: UploadFile = File(...)):
    settings = get_settings()

    if not _is_accepted(file.content_type or "", file.filename or ""):
        raise HTTPException(
            status_code=422,
            detail="Unsupported audio format. Accepted: mp3, wav, ogg, m4a, webm",
        )

    os.makedirs(settings.temp_audio_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or ".wav")[1].lower() or ".wav"
    temp_path = os.path.join(settings.temp_audio_dir, f"{uuid.uuid4()}{ext}")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 500MB limit")

    with open(temp_path, "wb") as f:
        f.write(content)

    job = await create_job()
    asyncio.create_task(run_job(job.job_id, temp_path))
    logger.info("upload_received job_id=%s file=%s bytes=%d", job.job_id, file.filename, len(content))

    return JobCreatedResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at.isoformat().replace("+00:00", "Z"),
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        created_at=job.created_at.isoformat().replace("+00:00", "Z"),
        updated_at=job.updated_at.isoformat().replace("+00:00", "Z"),
        task_id=job.task_id,
        error_message=job.error_message,
    )
