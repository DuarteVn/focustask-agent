import logging

from fastapi import APIRouter, HTTPException, Query

from app.db.repository import get_task_record, list_task_records
from app.models.schemas import (
    ExecutionFlow,
    TaskDetailResponse,
    TaskListResponse,
    TaskSummaryItem,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(task_id: str):
    record = await get_task_record(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskDetailResponse(
        task_id=record.task_id,
        created_at=record.created_at,
        detected_language=record.detected_language,
        audio_duration_seconds=record.audio_duration_seconds,
        raw_transcript=record.raw_transcript,
        objective=record.objective,
        checklist=record.checklist,
        flow=ExecutionFlow(
            input=record.flow_input,
            logic=record.flow_logic,
            output=record.flow_output,
        ),
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(limit: int = Query(default=20, ge=1, le=100)):
    records = await list_task_records(limit)
    items = [
        TaskSummaryItem(
            task_id=r.task_id,
            created_at=r.created_at,
            objective=r.objective,
            detected_language=r.detected_language,
        )
        for r in records
    ]
    return TaskListResponse(tasks=items, total=len(items))
