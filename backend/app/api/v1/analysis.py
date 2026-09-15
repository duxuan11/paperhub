"""论文级 AI 分析 API：Skills/Model/Prompt 配置、结果与执行。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import repositories
from app.api.v1.guards import ensure_no_active_job
from app.core.config import settings
from app.core.database import get_session
from app.core.security import require_auth
from app.schemas import (
    AIAnalysisConfigOut,
    AIAnalysisConfigUpdate,
    AIAnalysisOut,
    AIAnalysisResultOut,
    AIAnalysisRunRequest,
    TaskEnqueueOut,
)
from app.services import analysis as analysis_service
from app.services import prompt as prompt_service
from app.services import skill_registry
from app.workers import enqueue

router = APIRouter(
    prefix="/api/v1", tags=["ai-analysis"], dependencies=[Depends(require_auth)]
)


async def _config_out(session: AsyncSession, paper_id: str, config) -> AIAnalysisConfigOut:
    return AIAnalysisConfigOut(
        paper_id=paper_id,
        enabled=config.enabled if config else True,
        model=(config.model if config else "") or "",
        selected_skills=list(config.selected_skills or []) if config else [],
        custom_prompt=(config.custom_prompt if config else "") or "",
        default_model=settings.openai_model,
        default_skills=[prompt_service.DEFAULT_ANALYSIS_SKILL],
        available_skills=await skill_registry.list_options(session),
        updated_at=config.updated_at if config else None,
    )


async def _get_paper_or_404(session: AsyncSession, paper_id: str):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper


@router.get("/papers/{paper_id}/ai-analysis", response_model=AIAnalysisOut)
async def get_ai_analysis(
    paper_id: str, session: AsyncSession = Depends(get_session)
):
    """AI 分析页初始化：配置 + 已保存结果 + MinerU 是否就绪。"""
    paper = await _get_paper_or_404(session, paper_id)
    config = await analysis_service.get_config(session, paper_id)
    results = await repositories.list_analysis_results(session, paper_id)
    return AIAnalysisOut(
        paper_id=paper_id,
        parsed=bool(paper.markdown_path),
        config=await _config_out(session, paper_id, config),
        results=[AIAnalysisResultOut.model_validate(r) for r in results],
    )


@router.put(
    "/papers/{paper_id}/ai-analysis/config", response_model=AIAnalysisConfigOut
)
async def update_ai_analysis_config(
    paper_id: str,
    req: AIAnalysisConfigUpdate,
    session: AsyncSession = Depends(get_session),
):
    """保存论文级 AI 分析配置（Skills / Model / Custom Prompt / Enable）。"""
    await _get_paper_or_404(session, paper_id)
    await analysis_service.save_config(
        session,
        paper_id,
        enabled=req.enabled,
        model=req.model,
        selected_skills=req.selected_skills,
        custom_prompt=req.custom_prompt,
    )
    config = await analysis_service.get_config(session, paper_id)
    return await _config_out(session, paper_id, config)


@router.post("/papers/{paper_id}/ai-analysis/run", response_model=TaskEnqueueOut)
async def run_ai_analysis(
    paper_id: str,
    req: AIAnalysisRunRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    """执行 AI 分析：先保存随请求带来的配置，再入队后台任务。

    必须建立在 MinerU 解析结果之上；未解析完成时返回 409。
    """
    paper = await _get_paper_or_404(session, paper_id)
    if not paper.markdown_path:
        raise HTTPException(
            status_code=409, detail=analysis_service.MINERU_NOT_READY_MESSAGE
        )

    await ensure_no_active_job(session, paper_id, "analyze", "分析")

    if req is not None and req.model_dump(exclude_unset=True):
        await analysis_service.save_config(
            session,
            paper_id,
            enabled=req.enabled,
            model=req.model,
            selected_skills=req.selected_skills,
            custom_prompt=req.custom_prompt,
        )

    config = await analysis_service.get_config(session, paper_id)
    if config is not None and not config.enabled:
        raise HTTPException(
            status_code=400, detail="该论文已关闭 AI 分析，请先启用后再执行。"
        )

    job = await repositories.create_job(session, paper_id, "analyze")
    await enqueue.enqueue("analyze_paper", paper_id, job.id, "")
    return TaskEnqueueOut(job_id=job.id, paper_id=paper_id)
