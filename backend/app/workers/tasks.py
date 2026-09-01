"""Arq 后台任务：解析 / Figure 检测 / AI 分析 / 生成公众号 / 发布。"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from arq.connections import ArqRedis

from app import models, repositories
from app.core.database import async_session_factory
from app.core.logging import get_logger, log_event
from app.core.minio import storage
from app.services import article as article_service
from app.services import chat
from app.services import paper as paper_service
from app.services.llm import get_llm_service
from app.services.mineru import get_mineru_service
from app.services.skill import load_skill
from app.services.wechat import build_article_payload, get_publisher
from app.services.yolo import get_figure_service

log = get_logger("tasks")


async def _set_job(
    job_id: str, *, status=None, progress=None, error=None, start=False, finish=False
):
    async with async_session_factory() as session:
        job = await repositories.get_job(session, job_id)
        if not job:
            return
        if start:
            job.status = models.JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if error is not None:
            job.error = error
        if finish:
            job.finished_at = datetime.now(timezone.utc)
        await session.commit()


async def _set_paper_status(paper_id: str, status: models.PaperStatus):
    async with async_session_factory() as session:
        paper = await repositories.get_paper(session, paper_id)
        if paper:
            paper.status = status
            await session.commit()


async def parse_paper(ctx: dict, paper_id: str, job_id: str) -> dict:
    t0 = time.perf_counter()
    log_event(20, "task_start", paper_id=paper_id, job_id=job_id, task="parse")
    await _set_job(job_id, start=True, progress=5)
    await _set_paper_status(paper_id, models.PaperStatus.PARSING)
    try:
        async with async_session_factory() as session:
            paper = await repositories.get_paper(session, paper_id)
            if not paper or not paper.pdf_path:
                raise ValueError("论文 PDF 不存在")
            pdf_data = storage.get_bytes(paper.pdf_path)
            if not pdf_data:
                raise ValueError("PDF 内容读取失败")
            import tempfile
            from pathlib import Path

            tmpdir = Path(tempfile.mkdtemp())
            tmp_path = tmpdir / (paper.filename or "paper.pdf")
            tmp_path.write_bytes(pdf_data)

        await _set_job(job_id, progress=30)
        service = get_mineru_service()
        result = await service.parse_pdf(tmp_path)
        await _set_job(job_id, progress=70)
        async with async_session_factory() as session:
            await paper_service.store_parse_result(session, paper_id, result)
        await _set_job(
            job_id, progress=100, status=models.JobStatus.SUCCESS, finish=True
        )
        log_event(
            20,
            "task_done",
            paper_id=paper_id,
            job_id=job_id,
            task="parse",
            duration=round(time.perf_counter() - t0, 3),
        )

        # 解析成功后自动衔接 Figure 检测
        from app.workers import enqueue as enq

        async with async_session_factory() as session:
            next_job = await repositories.create_job(
                session, paper_id, "detect_figures"
            )
        await enq.enqueue("detect_figures", paper_id, next_job.id)
        return {"paper_id": paper_id, "status": "success", "source": result.source}
    except Exception as e:  # noqa: BLE001
        await _set_job(
            job_id, status=models.JobStatus.FAILED, error=str(e), finish=True
        )
        await _set_paper_status(paper_id, models.PaperStatus.FAILED)
        log_event(
            40,
            "task_failed",
            paper_id=paper_id,
            job_id=job_id,
            task="parse",
            error=str(e),
        )
        return {"paper_id": paper_id, "status": "failed", "error": str(e)}


async def detect_figures(ctx: dict, paper_id: str, job_id: str) -> dict:
    t0 = time.perf_counter()
    await _set_job(job_id, start=True, progress=5)
    await _set_paper_status(paper_id, models.PaperStatus.FIGURE_DETECTING)
    try:
        keys = storage.list_objects(f"{paper_id}/images/")
        if not keys:
            keys = [o for o in storage.list_objects(f"{paper_id}/") if "/images/" in o]
        await _set_job(job_id, progress=30)
        service = get_figure_service()
        items = [(k, _page_from_key(k)) for k in sorted(keys)]
        detected = await service.detect(items)
        await _set_job(job_id, progress=80)
        figs = [
            {
                "figure_number": i,
                "image_path": d.image_path,
                "caption": d.caption,
                "bbox": d.bbox,
                "type": d.type,
                "page": d.page,
            }
            for i, d in enumerate(detected, start=1)
        ]
        async with async_session_factory() as session:
            await paper_service.add_figures(session, paper_id, figs)
        await _set_job(
            job_id, progress=100, status=models.JobStatus.SUCCESS, finish=True
        )
        log_event(
            20,
            "task_done",
            paper_id=paper_id,
            job_id=job_id,
            task="detect_figures",
            duration=round(time.perf_counter() - t0, 3),
        )
        return {"paper_id": paper_id, "status": "success", "figures": len(figs)}
    except Exception as e:  # noqa: BLE001
        await _set_job(
            job_id, status=models.JobStatus.FAILED, error=str(e), finish=True
        )
        # 失败但不置 FAILED，保持 PARSED，允许重试
        await _set_paper_status(paper_id, models.PaperStatus.PARSED)
        log_event(
            40,
            "task_failed",
            paper_id=paper_id,
            job_id=job_id,
            task="detect_figures",
            error=str(e),
        )
        return {"paper_id": paper_id, "status": "failed", "error": str(e)}


def _page_from_key(key: str) -> int | None:
    import re

    m = re.search(r"image_(\d+)_", key)
    return int(m.group(1)) if m else None


async def analyze_paper(
    ctx: dict, paper_id: str, job_id: str, skill: str = "paper-summary"
) -> dict:
    t0 = time.perf_counter()
    await _set_job(job_id, start=True, progress=5)
    await _set_paper_status(paper_id, models.PaperStatus.ANALYZING)
    try:
        async with async_session_factory() as session:
            messages = await chat.build_messages(
                session,
                "请按照 Skill 要求完成这篇论文的完整分析。",
                paper_id=paper_id,
                skill_name=skill,
            )
            llm = get_llm_service()
            text = await llm.complete(messages)
            await _set_job(job_id, progress=80)
            paper = await repositories.get_paper(session, paper_id)
            if paper:
                paper.analysis = text
                paper.analysis_path = f"{paper_id}/analysis.md"
                storage.put_bytes(
                    paper.analysis_path, text.encode("utf-8"), "text/markdown"
                )
                paper.status = models.PaperStatus.ANALYZED
                await session.commit()
        await _set_job(
            job_id, progress=100, status=models.JobStatus.SUCCESS, finish=True
        )
        log_event(
            20,
            "task_done",
            paper_id=paper_id,
            job_id=job_id,
            task="analyze",
            duration=round(time.perf_counter() - t0, 3),
        )
        return {"paper_id": paper_id, "status": "success"}
    except Exception as e:  # noqa: BLE001
        await _set_job(
            job_id, status=models.JobStatus.FAILED, error=str(e), finish=True
        )
        await _set_paper_status(paper_id, models.PaperStatus.READY)
        log_event(
            40,
            "task_failed",
            paper_id=paper_id,
            job_id=job_id,
            task="analyze",
            error=str(e),
        )
        return {"paper_id": paper_id, "status": "failed", "error": str(e)}


async def generate_wechat_article(
    ctx: dict,
    paper_id: str,
    job_id: str,
    skill: str = "wechat-article",
    style: str = "科研论文解读",
) -> dict:
    t0 = time.perf_counter()
    await _set_job(job_id, start=True, progress=10)
    try:
        async with async_session_factory() as session:
            art = await article_service.generate_article(
                session, paper_id, skill_name=skill, style=style
            )
        await _set_job(
            job_id, progress=100, status=models.JobStatus.SUCCESS, finish=True
        )
        log_event(
            20,
            "task_done",
            paper_id=paper_id,
            job_id=job_id,
            task="generate_wechat",
            duration=round(time.perf_counter() - t0, 3),
        )
        return {"paper_id": paper_id, "status": "success", "article_id": art.id}
    except Exception as e:  # noqa: BLE001
        await _set_job(
            job_id, status=models.JobStatus.FAILED, error=str(e), finish=True
        )
        log_event(
            40,
            "task_failed",
            paper_id=paper_id,
            job_id=job_id,
            task="generate_wechat",
            error=str(e),
        )
        return {"paper_id": paper_id, "status": "failed", "error": str(e)}


async def publish_wechat_article(
    ctx: dict, article_id: str, job_id: str, publish: bool = False
) -> dict:
    t0 = time.perf_counter()
    await _set_job(job_id, start=True, progress=10)
    try:
        async with async_session_factory() as session:
            art = await repositories.get_article(session, article_id)
            if not art:
                raise ValueError(f"article not found: {article_id}")
            publisher = get_publisher()
            payload = build_article_payload(art.title or "未命名", art.content or "")
            rec = models.PublishRecord(
                article_id=article_id,
                platform="wechat",
                status=models.PublishStatus.PENDING,
            )
            session.add(rec)
            await session.flush()

            draft = await publisher.create_draft(payload)
            if draft.success:
                if publish:
                    pub = await publisher.publish(draft.external_id or "")
                    rec.external_id = pub.external_id
                    rec.status = (
                        models.PublishStatus.SUCCESS
                        if pub.success
                        else models.PublishStatus.FAILED
                    )
                    rec.error = pub.error
                    art.status = (
                        models.ArticleStatus.PUBLISHED if pub.success else art.status
                    )
                else:
                    rec.external_id = draft.external_id
                    rec.status = models.PublishStatus.SUCCESS
                    art.status = models.ArticleStatus.SENT_TO_PLATFORM
                rec.published_at = datetime.now(timezone.utc)
            else:
                rec.status = models.PublishStatus.FAILED
                rec.error = draft.error
            await session.commit()
        await _set_job(
            job_id, progress=100, status=models.JobStatus.SUCCESS, finish=True
        )
        log_event(
            20,
            "task_done",
            paper_id=art.paper_id,
            job_id=job_id,
            task="publish_wechat",
            duration=round(time.perf_counter() - t0, 3),
        )
        return {
            "article_id": article_id,
            "status": "success",
            "mock": publisher.is_mock(),
        }
    except Exception as e:  # noqa: BLE001
        await _set_job(
            job_id, status=models.JobStatus.FAILED, error=str(e), finish=True
        )
        log_event(
            40,
            "task_failed",
            paper_id=None,
            job_id=job_id,
            task="publish_wechat",
            error=str(e),
        )
        return {"article_id": article_id, "status": "failed", "error": str(e)}
