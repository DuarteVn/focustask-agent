import logging

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    await _ensure_schema()
    logger.info("DB pool ready")


async def _ensure_schema() -> None:
    # Live-DB migration for pre-existing deployments (data-model.md):
    #   ALTER TABLE jobs ADD COLUMN IF NOT EXISTS summary TEXT;
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id      TEXT PRIMARY KEY,
                status      TEXT NOT NULL DEFAULT 'pending',
                source      TEXT NOT NULL DEFAULT 'web',
                transcript  TEXT,
                summary     TEXT,
                objetivo    TEXT,
                checklist   JSONB,
                fluxo       JSONB,
                error_msg   TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS summary TEXT")


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB not initialized — call init_db() first")
    return _pool


async def close_db() -> None:
    if _pool:
        await _pool.close()
        logger.info("DB pool closed")
