"""文章 API（列表/编辑/润色/缩短/扩展/重新生成/封面）。"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories, schemas
from app.core.database import get_session
from app.core.minio import storage
from app.core.security import require_auth
from app.schemas import ArticleActionRequest, ArticleOut, ArticleUpdateRequest
from app.services import article as article_service
from app.services.llm import get_llm_service

router = APIRouter(
    prefix="/api/v1/articles", tags=["articles"], dependencies=[Depends(require_auth)]
)

# 公众号封面：支持的类型与大小上限（微信封面推荐 2.35:1，大小限制 < 10MB）
_COVER_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_MAX_COVER_BYTES = 10 * 1024 * 1024


def _cover_ext(content_type: str | None, filename: str | None) -> str | None:
    ext = _COVER_EXT.get((content_type or "").lower())
    if ext:
        return ext
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in {v for v in _COVER_EXT.values()} else None

ACTION_PROMPTS = {
    "polish": "请润色以下公众号文章，使语言更流畅、专业、易读，保持结构不变，输出完整 Markdown。",
    "shorten": "请精简以下公众号文章，压缩到原长度的一半左右，保留核心信息与结构，输出完整 Markdown。",
    "expand": "请扩展以下公众号文章，补充更多细节与背景，使内容更丰富，输出完整 Markdown。",
}


@router.get("", response_model=list[ArticleOut])
async def list_articles(
    paper_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session),
):
    return await repositories.list_articles(session, paper_id=paper_id, limit=limit)


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: str, session: AsyncSession = Depends(get_session)):
    art = await repositories.get_article(session, article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    return art


@router.patch("/{article_id}", response_model=ArticleOut)
async def update_article(
    article_id: str,
    req: ArticleUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    art = await repositories.get_article(session, article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(art, field, value)
    await session.commit()
    await session.refresh(art)
    return art


@router.post("/{article_id}/cover", response_model=ArticleOut)
async def upload_article_cover(
    article_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """上传公众号文章封面，写入对象存储并把 key 记到 article.cover_image。

    发布时该封面会被上传为微信永久素材，作为草稿 thumb_media_id。
    """
    art = await repositories.get_article(session, article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="封面文件为空")
    if len(data) > _MAX_COVER_BYTES:
        raise HTTPException(status_code=400, detail="封面图片不能超过 10MB")
    ext = _cover_ext(file.content_type, file.filename)
    if not ext:
        raise HTTPException(
            status_code=400, detail="封面仅支持 PNG / JPG / WEBP / GIF 图片"
        )
    key = f"articles/{article_id}/cover/{uuid.uuid4().hex[:12]}{ext}"
    storage.put_bytes(key, data, file.content_type or "image/png")
    art.cover_image = key
    await session.commit()
    await session.refresh(art)
    return art


@router.delete("/{article_id}/cover", response_model=ArticleOut)
async def delete_article_cover(
    article_id: str,
    session: AsyncSession = Depends(get_session),
):
    """清除文章封面配置（回退为「首图 / 默认封面」策略）。"""
    art = await repositories.get_article(session, article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    art.cover_image = None
    await session.commit()
    await session.refresh(art)
    return art


@router.post("/{article_id}/action", response_model=ArticleOut)
async def article_action(
    article_id: str,
    req: ArticleActionRequest,
    session: AsyncSession = Depends(get_session),
):
    art = await repositories.get_article(session, article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")

    if req.action == "regenerate":
        if not art.paper_id:
            raise HTTPException(
                status_code=400, detail="该文章无关联论文，无法重新生成"
            )
        new_art = await article_service.generate_article(
            session,
            art.paper_id,
            style=req.style or art.style or "科研论文解读",
            skill_name=art.skill or "wechat-article",
            extra_instructions=req.instruction,
        )
        return new_art

    prompt = ACTION_PROMPTS.get(req.action)
    if not prompt:
        raise HTTPException(status_code=400, detail="未知操作")
    if req.instruction:
        prompt += f"\n额外要求：{req.instruction}"

    llm = get_llm_service()
    content = art.content or ""
    result = await llm.complete(
        [
            {
                "role": "system",
                "content": "你是公众号文章编辑助手，输出 Markdown 格式。",
            },
            {"role": "user", "content": f"{prompt}\n\n文章内容：\n{content}"},
        ]
    )
    if result.strip():
        art.content = result
        art.title = article_service._extract_title(result, art.title or "未命名")
        art.summary = article_service._extract_summary(result) or art.summary
        await session.commit()
        await session.refresh(art)
    return art
