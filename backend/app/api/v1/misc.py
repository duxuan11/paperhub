"""健康检查 / Skills / 运行模式信息 / AI 分析提示词配置。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import require_auth
from app.schemas import AnalysisPromptOut, AnalysisPromptUpdate, HealthOut
from app.services import prompt as prompt_service
from app.services import skill_registry
from app.services.llm import llm_mode

router = APIRouter(prefix="/api/v1", tags=["misc"])


@router.get("/health", response_model=HealthOut)
async def health():
    return HealthOut(
        status="ok",
        version="0.1.0",
        auth_enabled=settings.auth_enabled,
        llm_mode=llm_mode(),
        mineru_mode="remote"
        if (settings.mineru_api_url and settings.mineru_api_key)
        else "mock",
        yolo_mode="onnx"
        if (settings.yolo_enabled and settings.yolo_model_path)
        else "heuristic",
        wechat_mode="real"
        if (settings.wechat_app_id and settings.wechat_app_secret)
        else "mock",
    )


@router.get("/settings", dependencies=[Depends(require_auth)])
async def settings_info():
    return {
        "llm_base_url": settings.openai_base_url,
        "llm_model": settings.openai_model,
        "llm_configured": bool(settings.openai_api_key),
        "mineru_configured": bool(settings.mineru_api_key),
        "wechat_configured": bool(settings.wechat_app_id),
        "yolo_configured": bool(settings.yolo_enabled and settings.yolo_model_path),
        "auth_enabled": settings.auth_enabled,
    }


@router.get(
    "/settings/analysis-prompt",
    response_model=AnalysisPromptOut,
    dependencies=[Depends(require_auth)],
)
async def get_analysis_prompt(session: AsyncSession = Depends(get_session)):
    """当前生效的 AI 分析配置（默认 Skill + 自定义提示词 + 可选 Skill 列表）。"""
    return await prompt_service.get_analysis_config(session)


@router.put(
    "/settings/analysis-prompt",
    response_model=AnalysisPromptOut,
    dependencies=[Depends(require_auth)],
)
async def update_analysis_prompt(
    req: AnalysisPromptUpdate, session: AsyncSession = Depends(get_session)
):
    """保存 AI 分析配置（prompt 传空串即清除自定义、回退默认）。"""
    try:
        return await prompt_service.save_analysis_config(
            session, skill=req.skill, prompt=req.prompt
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/settings/skills", dependencies=[Depends(require_auth)])
async def settings_skills(session: AsyncSession = Depends(get_session)):
    """供设置页「调用 Skill」入口使用：返回每个 Skill 的正文（含自定义）。"""
    return {"skills": await skill_registry.list_options(session)}
