"""论文相关 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories, schemas
from app.core.database import get_session
from app.core.minio import storage
from app.core.security import require_auth
from app.schemas import (
    AnalyzeRequest,
    FigureOut,
    GenerateArticleRequest,
    JobOut,
    PaperMeta,
    PaperOut,
    TaskEnqueueOut,
)
from app.services import paper as paper_service
from app.workers import enqueue

router = APIRouter(
    prefix="/api/v1/papers", tags=["papers"], dependencies=[Depends(require_auth)]
)


async def _create_paper_and_parse(
    session: AsyncSession, filename: str, data: bytes
) -> models.Paper:
    paper = await paper_service.create_paper_from_upload(session, filename, data)
    job = await repositories.create_job(session, paper.id, "parse")
    await enqueue.enqueue("parse_paper", paper.id, job.id)
    return paper


@router.post("/upload", response_model=PaperOut, status_code=201)
async def upload_paper(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    data = await file.read()
    if not data or data[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")
    return await _create_paper_and_parse(session, file.filename or "paper.pdf", data)


@router.post("/batch-upload", response_model=list[PaperOut], status_code=201)
async def batch_upload(
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    papers = []
    for f in files:
        data = await f.read()
        if not data or data[:4] != b"%PDF":
            continue
        papers.append(
            await _create_paper_and_parse(session, f.filename or "paper.pdf", data)
        )
    return papers


@router.get("", response_model=list[PaperOut])
async def list_papers(
    status: str | None = Query(None),
    query: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_session),
):
    return await repositories.list_papers(
        session, status=status, query=query, limit=limit, offset=offset
    )


@router.get("/{paper_id}", response_model=PaperOut)
async def get_paper(paper_id: str, session: AsyncSession = Depends(get_session)):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    return paper


@router.patch("/{paper_id}", response_model=PaperOut)
async def update_paper(
    paper_id: str, meta: PaperMeta, session: AsyncSession = Depends(get_session)
):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    for field, value in meta.model_dump(exclude_unset=True).items():
        setattr(paper, field, value)
    await session.commit()
    await session.refresh(paper)
    return paper


@router.get("/{paper_id}/markdown")
async def get_paper_markdown(
    paper_id: str, session: AsyncSession = Depends(get_session)
):
    paper = await repositories.get_paper(session, paper_id)
    if not paper or not paper.markdown_path:
        raise HTTPException(status_code=404, detail="Markdown 不存在")
    data = storage.get_bytes(paper.markdown_path)
    if not data:
        raise HTTPException(status_code=404, detail="Markdown 内容读取失败")
    return {"paper_id": paper_id, "markdown": data.decode("utf-8", errors="ignore")}


@router.get("/{paper_id}/figures", response_model=list[FigureOut])
async def get_paper_figures(
    paper_id: str, session: AsyncSession = Depends(get_session)
):
    return await repositories.list_figures(session, paper_id)


@router.get("/{paper_id}/analysis")
async def get_paper_analysis(
    paper_id: str, session: AsyncSession = Depends(get_session)
):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    return {"paper_id": paper_id, "analysis": paper.analysis or ""}


@router.post("/{paper_id}/parse", response_model=TaskEnqueueOut)
async def reparse_paper(paper_id: str, session: AsyncSession = Depends(get_session)):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    job = await repositories.create_job(session, paper_id, "parse")
    await enqueue.enqueue("parse_paper", paper_id, job.id)
    return TaskEnqueueOut(job_id=job.id, paper_id=paper_id)


@router.post("/{paper_id}/detect-figures", response_model=TaskEnqueueOut)
async def detect_figures(paper_id: str, session: AsyncSession = Depends(get_session)):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    job = await repositories.create_job(session, paper_id, "detect_figures")
    await enqueue.enqueue("detect_figures", paper_id, job.id)
    return TaskEnqueueOut(job_id=job.id, paper_id=paper_id)


@router.post("/{paper_id}/analyze", response_model=TaskEnqueueOut)
async def analyze_paper(
    paper_id: str,
    req: AnalyzeRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    skill = (req.skill if req else "paper-summary") or "paper-summary"
    job = await repositories.create_job(session, paper_id, "analyze")
    await enqueue.enqueue("analyze_paper", paper_id, job.id, skill)
    return TaskEnqueueOut(job_id=job.id, paper_id=paper_id)


@router.post("/{paper_id}/generate-wechat", response_model=TaskEnqueueOut)
async def generate_wechat(
    paper_id: str,
    req: GenerateArticleRequest | None = None,
    session: AsyncSession = Depends(get_session),
):
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="论文不存在")
    skill = (req.skill if req else "wechat-article") or "wechat-article"
    style = (req.style if req else "科研论文解读") or "科研论文解读"
    job = await repositories.create_job(session, paper_id, "generate_wechat")
    await enqueue.enqueue("generate_wechat_article", paper_id, job.id, skill, style)
    return TaskEnqueueOut(job_id=job.id, paper_id=paper_id)


@router.get("/{paper_id}/jobs", response_model=list[JobOut])
async def paper_jobs(paper_id: str, session: AsyncSession = Depends(get_session)):
    return await repositories.list_jobs(session, paper_id=paper_id)
