import json
import logging
from typing import Optional

from app.db.database import get_pool

logger = logging.getLogger(__name__)


async def create_job(job_id: str, source: str = "web") -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO jobs (job_id, status, source) VALUES ($1, 'pending', $2)",
            job_id, source,
        )


async def set_processing(job_id: str, transcript: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET status='processing', transcript=$1 WHERE job_id=$2",
            transcript, job_id,
        )


async def set_summary(job_id: str, summary: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET summary=$1 WHERE job_id=$2",
            summary, job_id,
        )


async def set_done(job_id: str, objetivo: str, checklist: list, fluxo: list) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET status='done', objetivo=$1, checklist=$2, fluxo=$3 WHERE job_id=$4",
            objetivo,
            json.dumps(checklist, ensure_ascii=False),
            json.dumps(fluxo, ensure_ascii=False),
            job_id,
        )


async def set_error(job_id: str, error: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE jobs SET status='error', error_msg=$1 WHERE job_id=$2",
            error, job_id,
        )


async def get_job(job_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM jobs WHERE job_id=$1", job_id)
        if row is None:
            return None
        d = dict(row)
        for field in ("checklist", "fluxo"):
            if isinstance(d.get(field), str):
                d[field] = json.loads(d[field])
        return d
