import asyncpg
from app.core.config import get_settings

_POOL: asyncpg.Pool | None = None


def get_pool() -> asyncpg.Pool:
    if _POOL is None:
        raise RuntimeError("DB pool not initialized — call init_db() first")
    return _POOL


async def init_db() -> None:
    global _POOL
    _POOL = await asyncpg.create_pool(dsn=get_settings().database_url)
    async with _POOL.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS task_records (
                task_id                 TEXT PRIMARY KEY,
                created_at              TEXT NOT NULL,
                audio_duration_seconds  REAL,
                raw_transcript          TEXT NOT NULL,
                detected_language       TEXT NOT NULL,
                objective               TEXT NOT NULL,
                checklist               TEXT NOT NULL,
                flow_input              TEXT NOT NULL,
                flow_logic              TEXT NOT NULL,
                flow_output             TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_records_created_at
                ON task_records (created_at DESC)
        """)


async def close_db() -> None:
    global _POOL
    if _POOL is not None:
        await _POOL.close()
        _POOL = None
