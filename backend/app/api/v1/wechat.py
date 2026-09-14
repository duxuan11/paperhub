"""微信公众号发布 API。

推送是异步的（Arq 任务），接口只负责落一条 PublishRecord + 入队，
真实结果通过 GET /wechat/records 查询（前端轮询该接口拿成功/失败与错误原因）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories, schemas
from app.api.v1.guards import ensure_no_active_job
from app.core.database import get_session
from app.core.security import require_auth
from app.schemas import WeChatRequest, WeChatDraftOut
from app.services.wechat import get_publisher
from app.workers import enqueue

router = APIRouter(
    prefix="/api/v1/wechat", tags=["wechat"], dependencies=[Depends(require_auth)]
)


async def _submit(
    session: AsyncSession, req: WeChatRequest, publish: bool
) -> WeChatDraftOut:
    art = await repositories.get_article(session, req.article_id)
    if not art:
        raise HTTPException(status_code=404, detail="文章不存在")

    await ensure_no_active_job(session, art.paper_id, "publish_wechat", "发布")

    rec = models.PublishRecord(
        article_id=req.article_id,
        platform="wechat",
        status=models.PublishStatus.PENDING,
    )
    session.add(rec)
    await session.commit()
    await session.refresh(rec)

    job = await repositories.create_job(session, art.paper_id, "publish_wechat")
    await enqueue.enqueue(
        "publish_wechat_article", req.article_id, job.id, publish, rec.id
    )
    return WeChatDraftOut(
        record_id=rec.id,
        article_id=req.article_id,
        external_id=None,
        status=str(models.PublishStatus.PENDING.value),
        mock=get_publisher().is_mock(),
    )


@router.post("/draft", response_model=WeChatDraftOut)
async def send_to_draft(
    req: WeChatRequest,
    session: AsyncSession = Depends(get_session),
):
    """把文章发送到公众号草稿箱（不发布）。"""
    return await _submit(session, req, publish=False)


@router.post("/publish", response_model=WeChatDraftOut)
async def publish_article(
    req: WeChatRequest,
    session: AsyncSession = Depends(get_session),
):
    """创建草稿后继续正式发布（需公众号发布权限）。"""
    return await _submit(session, req, publish=True)


@router.get("/records", response_model=list[schemas.PublishRecordOut])
async def list_records(
    article_id: str | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):
    from sqlalchemy import select

    stmt = select(models.PublishRecord).order_by(models.PublishRecord.created_at.desc())
    if article_id:
        stmt = stmt.where(models.PublishRecord.article_id == article_id)
    return (await session.scalars(stmt.limit(min(limit, 500)))).all()
