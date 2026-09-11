"""API 层公共守卫。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import repositories


async def ensure_no_active_job(
    session: AsyncSession, paper_id: str | None, job_type: str, label: str
) -> None:
    """同一论文下同类型任务仍在排队/执行时，拒绝重复触发。"""
    if not paper_id:
        return
    if await repositories.get_active_job(session, paper_id, job_type):
        raise HTTPException(status_code=409, detail=f"{label}任务已在运行中，请稍候")
