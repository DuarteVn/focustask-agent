import json
from dataclasses import dataclass
from typing import Optional

import asyncpg
from app.db.database import get_pool


@dataclass
class TaskRecord:
    task_id: str
    created_at: str
    raw_transcript: str
    detected_language: str
    objective: str
    checklist: list[str]
    flow_input: str
    flow_logic: str
    flow_output: str
    audio_duration_seconds: Optional[float] = None


def _row_to_record(row: asyncpg.Record) -> TaskRecord:
    return TaskRecord(
        task_id=row["task_id"],
        created_at=row["created_at"],
        audio_duration_seconds=row["audio_duration_seconds"],
        raw_transcript=row["raw_transcript"],
        detected_language=row["detected_language"],
        objective=row["objective"],
        checklist=json.loads(row["checklist"]),
        flow_input=row["flow_input"],
        flow_logic=row["flow_logic"],
        flow_output=row["flow_output"],
    )


async def insert_task_record(record: TaskRecord) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO task_records
               (task_id, created_at, audio_duration_seconds, raw_transcript,
                detected_language, objective, checklist, flow_input, flow_logic, flow_output)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            record.task_id,
            record.created_at,
            record.audio_duration_seconds,
            record.raw_transcript,
            record.detected_language,
            record.objective,
            json.dumps(record.checklist, ensure_ascii=False),
            record.flow_input,
            record.flow_logic,
            record.flow_output,
        )


async def get_task_record(task_id: str) -> Optional[TaskRecord]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM task_records WHERE task_id = $1", task_id
        )
        return _row_to_record(row) if row else None


async def list_task_records(limit: int = 20) -> list[TaskRecord]:
    limit = min(limit, 100)
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM task_records ORDER BY created_at DESC LIMIT $1", limit
        )
        return [_row_to_record(r) for r in rows]
