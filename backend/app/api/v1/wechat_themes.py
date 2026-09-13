"""微信公众号推文主题（Theme）API。

- ``GET    /api/v1/wechat/themes``                 主题列表（内置 + 自定义）
- ``POST   /api/v1/wechat/themes``                 创建自定义主题
- ``GET    /api/v1/wechat/themes/{id}``            单个主题
- ``PUT    /api/v1/wechat/themes/{id}``            更新自定义主题（内置禁止）
- ``DELETE /api/v1/wechat/themes/{id}``            删除自定义主题（内置禁止）
- ``POST   /api/v1/wechat/themes/{id}/duplicate``  复制为自定义主题
- ``POST   /api/v1/wechat/themes/{id}/set-default`` 设为默认主题
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import require_auth
from app.schemas import (
    WeChatThemeCreate,
    WeChatThemeDuplicate,
    WeChatThemeUpdate,
    WechatThemeOut,
)
from app.services import wechat_theme as theme_service

router = APIRouter(
    prefix="/api/v1/wechat/themes",
    tags=["wechat-themes"],
    dependencies=[Depends(require_auth)],
)


@router.get("", response_model=list[WechatThemeOut])
async def list_wechat_themes(session: AsyncSession = Depends(get_session)):
    """主题列表：内置主题在前，自定义主题在后。前端据此渲染模板卡片与预览。"""
    rows = await theme_service.list_themes(session)
    return [theme_service.to_out(row) for row in rows]


@router.post("", response_model=WechatThemeOut, status_code=201)
async def create_wechat_theme(
    req: WeChatThemeCreate,
    session: AsyncSession = Depends(get_session),
):
    row = await theme_service.create_theme(
        session,
        name=req.name,
        description=req.description,
        config=req.config.model_dump() if req.config else None,
        is_default=req.is_default,
    )
    return theme_service.to_out(row)


@router.get("/{theme_id}", response_model=WechatThemeOut)
async def get_wechat_theme(
    theme_id: str,
    session: AsyncSession = Depends(get_session),
):
    row = await theme_service.get_theme_or_none(session, theme_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"主题不存在: {theme_id}")
    return theme_service.to_out(row)


@router.put("/{theme_id}", response_model=WechatThemeOut)
async def update_wechat_theme(
    theme_id: str,
    req: WeChatThemeUpdate,
    session: AsyncSession = Depends(get_session),
):
    try:
        row = await theme_service.update_theme(
            session,
            theme_id,
            name=req.name,
            description=req.description,
            config=req.config.model_dump() if req.config else None,
        )
    except theme_service.WeChatThemeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except theme_service.BuiltinThemeImmutable as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return theme_service.to_out(row)


@router.delete("/{theme_id}", status_code=204)
async def delete_wechat_theme(
    theme_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        await theme_service.delete_theme(session, theme_id)
    except theme_service.WeChatThemeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except theme_service.BuiltinThemeImmutable as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return None


@router.post("/{theme_id}/duplicate", response_model=WechatThemeOut, status_code=201)
async def duplicate_wechat_theme(
    theme_id: str,
    req: WeChatThemeDuplicate | None = None,
    session: AsyncSession = Depends(get_session),
):
    try:
        row = await theme_service.duplicate_theme(
            session, theme_id, name=req.name if req else None
        )
    except theme_service.WeChatThemeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return theme_service.to_out(row)


@router.post("/{theme_id}/set-default", response_model=WechatThemeOut)
async def set_default_wechat_theme(
    theme_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        row = await theme_service.set_default_theme(session, theme_id)
    except theme_service.WeChatThemeNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return theme_service.to_out(row)
