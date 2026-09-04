"""微信公众号发布 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories, schemas
from app.core.database import get_session
from app.core.security import require_auth
from app.schemas import WeChatRequest, WeChatDraftOut
from app.workers import enqueue

router = APIRouter(prefix="/api/v1/wechat", tags=["wechat"], dependencies=[Depends(require_auth)])


@router.post("/draft", response_model=WeChatDraftOut)
async def send_to_draft(
    req: WeChatRequest,
    session: AsyncSession = Depends(get_session),
):
    art = await repositories.get_article(session, req.article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    job = await repositories.create_job(session, art.paper_id, "publish_wechat")
    await enqueue.enqueue("publish_wechat_article", req.article_id, job.id, req.publish)
    return WeChatDraftOut(
        record_id=job.id, article_id=req.article_id, external_id=None, status="PENDING", mock=True
    )


@router.post("/publish", response_model=WeChatDraftOut)
async def publish_article(
    req: WeChatRequest,
    session: AsyncSession = Depends(get_session),
):
    art = await repositories.get_article(session, req.article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")
    job = await repositories.create_job(session, art.paper_id, "publish_wechat")
    await enqueue.enqueue("publish_wechat_article", req.article_id, job.id, True)
    return WeChatDraftOut(
        record_id=job.id, article_id=req.article_id, external_id=None, status="PENDING", mock=True
    )


@router.get("/records", response_model=list[schemas.PublishRecordOut])
async def list_records(
    article_id: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select

    stmt = select(models.PublishRecord).order_by(models.PublishRecord.created_at.desc())
    if article_id:
        stmt = stmt.where(models.PublishRecord.article_id == article_id)
    return (await session.scalars(stmt.limit(100))).all()
