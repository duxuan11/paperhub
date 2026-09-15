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


async def get_active_job(
    session: AsyncSession, paper_id: str, job_type: str
) -> models.Job | None:
    """返回该论文下指定类型仍在排队/执行中的任务（用于拦截重复触发）。"""
    stmt = (
        select(models.Job)
        .where(
            models.Job.paper_id == paper_id,
            models.Job.job_type == job_type,
            models.Job.status.in_([models.JobStatus.PENDING, models.JobStatus.RUNNING]),
        )
        .order_by(models.Job.created_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


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


async def list_wechat_themes(
    session: AsyncSession,
) -> Sequence[models.WeChatArticleTheme]:
    stmt = select(models.WeChatArticleTheme).order_by(
        models.WeChatArticleTheme.is_builtin.desc(),
        models.WeChatArticleTheme.created_at.asc(),
    )
    return (await session.scalars(stmt)).all()


async def get_wechat_theme(
    session: AsyncSession, theme_id: str
) -> models.WeChatArticleTheme | None:
    return await session.get(models.WeChatArticleTheme, theme_id)


async def get_setting(session: AsyncSession, key: str) -> str | None:
    row = await session.get(models.AppSetting, key)
    return row.value if row else None


async def set_setting(session: AsyncSession, key: str, value: str | None) -> None:
    """写入或覆盖一个配置项（value 为 None/空串时视为清除）。"""
    row = await session.get(models.AppSetting, key)
    if row is None:
        row = models.AppSetting(key=key)
        session.add(row)
    row.value = value
    await session.commit()


async def list_custom_skills(
    session: AsyncSession,
) -> Sequence[models.CustomSkill]:
    stmt = select(models.CustomSkill).order_by(models.CustomSkill.created_at.asc())
    return (await session.scalars(stmt)).all()


async def get_custom_skill(
    session: AsyncSession, name: str
) -> models.CustomSkill | None:
    return await session.get(models.CustomSkill, name)


async def get_ai_analysis_config(
    session: AsyncSession, paper_id: str
) -> models.AIAnalysisConfig | None:
    return await session.get(models.AIAnalysisConfig, paper_id)


async def upsert_ai_analysis_config(
    session: AsyncSession,
    paper_id: str,
    *,
    enabled: bool | None = None,
    model: str | None = None,
    selected_skills: list[str] | None = None,
    custom_prompt: str | None = None,
) -> models.AIAnalysisConfig:
    """按字段增量更新论文级 AI 分析配置（None 表示保持原值）。"""
    row = await session.get(models.AIAnalysisConfig, paper_id)
    if row is None:
        row = models.AIAnalysisConfig(paper_id=paper_id)
        session.add(row)
    if enabled is not None:
        row.enabled = enabled
    if model is not None:
        row.model = model
    if selected_skills is not None:
        row.selected_skills = selected_skills
    if custom_prompt is not None:
        row.custom_prompt = custom_prompt
    await session.commit()
    await session.refresh(row)
    return row


async def list_analysis_results(
    session: AsyncSession, paper_id: str
) -> Sequence[models.AIAnalysisResult]:
    stmt = (
        select(models.AIAnalysisResult)
        .where(models.AIAnalysisResult.paper_id == paper_id)
        .order_by(models.AIAnalysisResult.created_at.asc())
    )
    return (await session.scalars(stmt)).all()


async def upsert_analysis_result(
    session: AsyncSession,
    paper_id: str,
    skill: str,
    content: str,
    model: str | None = None,
) -> models.AIAnalysisResult:
    """写入某个 (论文, Skill) 的分析结果，重复运行时覆盖旧结果。"""
    row = await session.get(models.AIAnalysisResult, (paper_id, skill))
    if row is None:
        row = models.AIAnalysisResult(paper_id=paper_id, skill=skill)
        session.add(row)
    row.content = content
    row.model = model
    await session.commit()
    await session.refresh(row)
    return row
