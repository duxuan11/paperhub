"""健康检查 / Skills / 运行模式信息。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import require_auth
from app.schemas import HealthOut
from app.services.llm import llm_mode
from app.services.skill import list_skills

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


@router.get("/skills", dependencies=[Depends(require_auth)])
async def skills():
    return {"skills": list_skills()}


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
