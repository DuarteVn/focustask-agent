import datetime
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response

from app.db.repository import get_job
from app.models.schemas import JobStatus, StructuredOutput
from app.services import markdown_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    """Job status polling — backs the async web flow (contracts/api.md)."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    status = job["status"]
    structured = None
    if status == "done" and job.get("objetivo") is not None:
        structured = StructuredOutput(
            objetivo=job["objetivo"],
            checklist=job.get("checklist") or [],
            fluxo=job.get("fluxo") or [],
        )

    return JobStatus(
        job_id=job_id,
        status=status,
        structured=structured,
        transcript=job.get("transcript"),
        error=job.get("error_msg"),
        markdown_url=f"/api/jobs/{job_id}/download.md" if status == "done" else None,
    )


@router.get("/{job_id}/download.md")
async def download_markdown(job_id: str) -> Response:
    """Obsidian-ready Markdown download; rendered on the fly, nothing on disk."""
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "done":
        raise HTTPException(status_code=409, detail=f"Job not ready — current status: {job['status']}")

    md = markdown_service.render(
        job.get("objetivo") or "",
        job.get("checklist") or [],
        job.get("fluxo") or [],
    )
    filename = markdown_service.make_filename(
        job.get("objetivo") or "", job_id, datetime.date.today()
    )
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )
