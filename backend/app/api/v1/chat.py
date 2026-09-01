"""Chat 与 Agent API（SSE 流式）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import repositories
from app.core.database import get_session
from app.core.minio import storage
from app.core.security import require_auth
from app.schemas import ChatRequest
from app.services import chat as chat_service

router = APIRouter(
    prefix="/api/v1", tags=["chat"], dependencies=[Depends(require_auth)]
)


def _sse(deltas):
    async def gen():
        async for text in deltas:
            yield f"data: {json.dumps({'delta': text, 'done': False}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'delta': '', 'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/chat")
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    deltas = chat_service.stream_chat(
        session,
        req.message,
        paper_id=req.paper_id,
        skill_name=req.skill,
        history=req.history,
    )
    return _sse(deltas)


@router.post("/agent")
async def agent(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    """自由形式 Agent：默认带入最近 5 篇论文的摘要与标题作为上下文。"""
    papers = await repositories.list_papers(session, limit=5)
    ctx: list[str] = []
    for p in papers:
        ctx.append(
            f"- 论文《{p.title or p.filename or p.id}》 (id={p.id}, 状态={p.status.value})"
        )
        if p.abstract:
            ctx.append(f"  摘要：{p.abstract[:500]}")
    system_ctx = "\n".join(ctx) or "暂无论文"
    message = req.message + "\n\n（可参考的最近论文：\n" + system_ctx + "\n）"

    deltas = chat_service.stream_chat(
        session,
        message,
        paper_id=req.paper_id,
        skill_name=req.skill,
        history=req.history,
    )
    return _sse(deltas)
