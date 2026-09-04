"""任务 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import repositories, schemas
from app.core.database import get_session
from app.core.security import require_auth

router = APIRouter(
    prefix="/api/v1/jobs", tags=["jobs"], dependencies=[Depends(require_auth)]
)


@router.get("", response_model=list[schemas.JobOut])
async def list_jobs(
    paper_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session),
):
    return await repositories.list_jobs(session, paper_id=paper_id, limit=limit)


@router.get("/{job_id}", response_model=schemas.JobOut)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)):
    job = await repositories.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job
