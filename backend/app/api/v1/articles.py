"""文章 API（列表/编辑/润色/缩短/扩展/重新生成）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories, schemas
from app.core.database import get_session
from app.core.security import require_auth
from app.schemas import ArticleActionRequest, ArticleOut, ArticleUpdateRequest
from app.services import article as article_service
from app.services.llm import get_llm_service

router = APIRouter(
    prefix="/api/v1/articles", tags=["articles"], dependencies=[Depends(require_auth)]
)

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
