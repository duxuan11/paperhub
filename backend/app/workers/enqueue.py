"""任务入队辅助。"""

from __future__ import annotations

from app.core.redis import get_arq_pool


async def enqueue(job_name: str, *args, **kwargs) -> str:
    pool = await get_arq_pool()
    job = await pool.enqueue_job(job_name, *args, **kwargs)
    return job.job_id
