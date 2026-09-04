"""仓储层：封装数据访问。"""

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


async def get_paper(session: AsyncSession, paper_id: str) -> models.Paper | None:
    return await session.get(models.Paper, paper_id)


async def list_papers(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    query: str | None = None,
) -> Sequence[models.Paper]:
    stmt = select(models.Paper).order_by(models.Paper.created_at.desc())
    if status:
        stmt = stmt.where(models.Paper.status == status)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            models.Paper.title.ilike(like) | models.Paper.filename.ilike(like)
        )
    stmt = stmt.limit(limit).offset(offset)
    return (await session.scalars(stmt)).all()


async def create_job(
    session: AsyncSession, paper_id: str | None, job_type: str
) -> models.Job:
    job = models.Job(paper_id=paper_id, job_type=job_type)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: str) -> models.Job | None:
    return await session.get(models.Job, job_id)


async def list_jobs(
    session: AsyncSession, paper_id: str | None = None, limit: int = 100
) -> Sequence[models.Job]:
    stmt = select(models.Job).order_by(models.Job.created_at.desc())
    if paper_id:
        stmt = stmt.where(models.Job.paper_id == paper_id)
    return (await session.scalars(stmt.limit(limit))).all()


async def list_figures(session: AsyncSession, paper_id: str) -> Sequence[models.Figure]:
    stmt = (
        select(models.Figure)
        .where(models.Figure.paper_id == paper_id)
        .order_by(
            models.Figure.figure_number.asc().nullslast(),
            models.Figure.created_at.asc(),
        )
    )
    return (await session.scalars(stmt)).all()


async def get_article(session: AsyncSession, article_id: str) -> models.Article | None:
    return await session.get(models.Article, article_id)


async def list_articles(
    session: AsyncSession, paper_id: str | None = None, limit: int = 100
) -> Sequence[models.Article]:
    stmt = select(models.Article).order_by(models.Article.created_at.desc())
    if paper_id:
        stmt = stmt.where(models.Article.paper_id == paper_id)
    return (await session.scalars(stmt.limit(limit))).all()
