"""Arq 后台任务：解析 / Figure 检测 / AI 分析 / 生成公众号 / 发布。"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

from arq.connections import ArqRedis

from app import models, repositories
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger, log_event
from app.core.minio import storage
from app.core.redis import get_arq_pool
from app.services import article as article_service
from app.services import chat
from app.services import paper as paper_service
from app.services import prompt as prompt_service
from app.services.figures import group_figure_numbers, parse_figure_refs
from app.services.llm import get_llm_service
from app.services.mineru import get_mineru_service
from app.services.skill import load_skill
from app.services.wechat import build_article_payload, get_publisher
from app.services.yolo import (
    HeuristicFigureService,
    RENDER_ZOOM,
    OnnxYoloService,
    crop_page_png,
    get_figure_service,
    render_pdf_pages,
)
from publishers.wechat.cover import default_cover_png

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

        pdf_data = await _read_pdf_bytes(paper_id)
        service = get_figure_service()

        figs: list[dict] = []
        source = "md"
        if isinstance(service, OnnxYoloService) and pdf_data:
            try:
                figs, source = await _detect_figures_on_pages(
                    service, paper_id, pdf_data
                )
            except Exception as e:  # noqa: BLE001
                log.warning("YOLO 整页检测失败，回退 md: %s", e)
                figs, source = [], "md"

        if not figs:
            items, captions = await _ordered_figure_items(paper_id, keys)
            fallback_service = (
                HeuristicFigureService()
                if isinstance(service, OnnxYoloService)
                else service
            )
            detected = await fallback_service.detect(items)
            figs = _build_md_figs(detected, captions)
            source = "md"

        await _set_job(job_id, progress=80)
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
            source=source,
            figures=len(figs),
            duration=round(time.perf_counter() - t0, 3),
        )
        return {
            "paper_id": paper_id,
            "status": "success",
            "figures": len(figs),
            "source": source,
        }
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


async def _read_pdf_bytes(paper_id: str) -> bytes | None:
    async with async_session_factory() as session:
        paper = await repositories.get_paper(session, paper_id)
        if not paper or not paper.pdf_path:
            return None
        return storage.get_bytes(paper.pdf_path)


async def _detect_figures_on_pages(
    service: OnnxYoloService,
    paper_id: str,
    pdf_data: bytes,
) -> tuple[list[dict], str]:
    """整页渲染 + YOLO 检测 Figure；检不到则返回空（由调用方回退 md）。"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        pages = render_pdf_pages(pdf_data, td)
        detections = await service.detect_pages(pages)

    figs: list[dict] = []
    for i, d in enumerate(detections, start=1):
        if not d.bbox:
            continue
        bbox_pdf = [round(v / RENDER_ZOOM, 2) for v in d.bbox]
        png = crop_page_png(pdf_data, (d.page or 1) - 1, bbox_pdf)
        name = f"page{d.page}_fig{i}.png"
        key = f"{paper_id}/figures/{name}"
        storage.put_bytes(key, png, "image/png")
        figs.append(
            {
                "figure_number": i,
                "image_path": key,
                "caption": None,
                "bbox": bbox_pdf,
                "type": d.type,
                "page": d.page,
            }
        )
    return figs, "yolo"


def _build_md_figs(detected: list, captions: dict[str, str]) -> list[dict]:
    """把 markdown 顺序检测出的图转成 DB 行（同图注子图共享编号）。"""
    caption_seq = [
        captions.get(d.image_path) or d.caption or f"Figure {i}"
        for i, d in enumerate(detected, start=1)
    ]
    numbers = group_figure_numbers(caption_seq)
    return [
        {
            "figure_number": numbers[i - 1],
            "image_path": d.image_path,
            "caption": caption_seq[i - 1],
            "bbox": d.bbox,
            "type": d.type,
            "page": d.page,
        }
        for i, d in enumerate(detected, start=1)
    ]


async def _ordered_figure_items(
    paper_id: str, keys: list[str]
) -> tuple[list[tuple[str, int | None]], dict[str, str]]:
    """按 markdown 中图片出现顺序返回 (object_key, page) 列表与图注映射。

    未在 markdown 中被引用的图片（多为 MinerU 冗余子图）不纳入 Figure；
    markdown 无图片引用时回退为旧的存储顺序枚举。
    """
    md = ""
    async with async_session_factory() as session:
        paper = await repositories.get_paper(session, paper_id)
        if paper and paper.markdown_path:
            raw = storage.get_bytes(paper.markdown_path)
            if raw:
                md = raw.decode("utf-8", errors="ignore")

    key_by_basename = {k.rsplit("/", 1)[-1]: k for k in keys}
    captions: dict[str, str] = {}
    items: list[tuple[str, int | None]] = []
    if md:
        for ref in parse_figure_refs(md):
            key = key_by_basename.get(ref["image"])
            if not key:
                continue
            items.append((key, _page_from_key(key)))
            if ref.get("caption"):
                captions[key] = ref["caption"]
    if not items:
        items = [(k, _page_from_key(k)) for k in sorted(keys)]
    return items, captions


def _page_from_key(key: str) -> int | None:
    import re

    m = re.search(r"image_(\d+)_", key)
    return int(m.group(1)) if m else None


async def analyze_paper(
    ctx: dict, paper_id: str, job_id: str, skill: str = ""
) -> dict:
    t0 = time.perf_counter()
    await _set_job(job_id, start=True, progress=5)
    await _set_paper_status(paper_id, models.PaperStatus.ANALYZING)
    try:
        async with async_session_factory() as session:
            # 设置页保存的「AI 分析」配置：默认 Skill + 自定义提示词
            skill_name, extra_prompt = await prompt_service.resolve_for_analysis(
                session, skill
            )
            messages = await chat.build_messages(
                session,
                "请按照 Skill 要求完成这篇论文的完整分析。",
                paper_id=paper_id,
                skill_name=skill_name,
                extra_system=extra_prompt,
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
            skill=skill_name,
            custom_prompt=bool(extra_prompt),
            duration=round(time.perf_counter() - t0, 3),
        )
        return {"paper_id": paper_id, "status": "success", "skill": skill_name}
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


def _cover_source(
    images: list[str], cover_image: str | None = None
) -> tuple[bytes, str]:
    """选封面素材：文章显式封面 > 文章首图 > 内置渐变封面。"""
    candidates = ([cover_image] if cover_image else []) + list(images)
    for key in candidates:
        if not key:
            continue
        data = storage.get_bytes(key)
        if data:
            return data, key.rsplit("/", 1)[-1]
    return default_cover_png(), "paperhub-default-cover.png"


async def _upload_content_images(publisher, images: list[str]) -> dict[str, str]:
    """把正文中的 {{figure:N}} 占位符映射为微信可访问的图片 URL。

    正文图片必须先经 /cgi-bin/media/uploadimg 换成 mmbiz URL，
    否则微信侧拿不到图（MinIO / localhost 地址微信无法访问）。
    """
    mapping: dict[str, str] = {}
    for idx, key in enumerate(images):
        data = storage.get_bytes(key)
        if not data:
            log.warning("正文图片读取失败，跳过: %s", key)
            continue
        try:
            url = await publisher.upload_content_image(data, key.rsplit("/", 1)[-1])
        except Exception as e:  # noqa: BLE001
            log.warning("正文图片上传微信失败，跳过: %s (%s)", key, e)
            continue
        mapping[f"{{{{figure:{idx}}}}}"] = url
    return mapping


async def _upload_cover_cached(publisher, data: bytes, filename: str) -> str:
    """上传封面永久素材，并按内容哈希缓存 media_id，避免重复上传。"""
    cache_key = f"wechat:cover:{hashlib.sha1(data).hexdigest()[:16]}"
    pool = None
    try:
        pool = await get_arq_pool()
        cached = await pool.get(cache_key)
        if cached:
            return cached.decode() if isinstance(cached, bytes) else str(cached)
    except Exception as e:  # noqa: BLE001
        log.warning("封面 media_id 缓存读取失败: %s", e)

    media_id = await publisher.upload_cover(data, filename)
    if pool is not None:
        try:
            await pool.set(cache_key, media_id)
        except Exception as e:  # noqa: BLE001
            log.warning("封面 media_id 缓存写入失败: %s", e)
    return media_id


async def _ensure_thumb_media_id(
    publisher, images: list[str], cover_image: str | None = None
) -> str:
    """草稿封面 thumb_media_id（图文草稿必填，否则 draft/add 报 40007）。

    优先级：
    1. 文章显式配置的封面（用户在编辑器里上传/选择的 cover_image）；
    2. 全局配置的 WECHAT_THUMB_MEDIA_ID；
    3. 文章首图；
    4. 内置渐变封面。

    media_id 按封面内容哈希缓存到 Redis，避免每次推送重复上传。
    """
    if cover_image:
        data = storage.get_bytes(cover_image)
        if data:
            return await _upload_cover_cached(
                publisher, data, cover_image.rsplit("/", 1)[-1]
            )
        log.warning("文章封面读取失败，回退默认封面选择: %s", cover_image)

    if settings.wechat_thumb_media_id:
        return settings.wechat_thumb_media_id

    data, filename = _cover_source(images)
    return await _upload_cover_cached(publisher, data, filename)


async def _create_publish_record(article_id: str) -> str:
    async with async_session_factory() as session:
        rec = models.PublishRecord(
            article_id=article_id,
            platform="wechat",
            status=models.PublishStatus.PENDING,
        )
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec.id


async def _finish_publish_record(
    record_id: str | None,
    status: models.PublishStatus,
    *,
    external_id: str | None = None,
    error: str | None = None,
) -> None:
    if not record_id:
        return
    async with async_session_factory() as session:
        rec = await session.get(models.PublishRecord, record_id)
        if not rec:
            return
        rec.status = status
        rec.external_id = external_id
        rec.error = error
        rec.published_at = datetime.now(timezone.utc)
        await session.commit()


async def _set_article_status(article_id: str, status: models.ArticleStatus) -> None:
    async with async_session_factory() as session:
        art = await repositories.get_article(session, article_id)
        if art:
            art.status = status
            await session.commit()


async def _publish_failed(
    job_id: str, error: str, article_id: str, paper_id: str | None, publisher, t0: float
) -> dict:
    await _set_job(
        job_id, progress=100, status=models.JobStatus.FAILED, error=error, finish=True
    )
    log_event(
        40,
        "task_failed",
        paper_id=paper_id,
        job_id=job_id,
        task="publish_wechat",
        error=error,
        duration=round(time.perf_counter() - t0, 3),
    )
    return {
        "article_id": article_id,
        "status": "failed",
        "error": error,
        "mock": publisher.is_mock(),
    }


async def publish_wechat_article(
    ctx: dict,
    article_id: str,
    job_id: str,
    publish: bool = False,
    record_id: str | None = None,
) -> dict:
    """推送文章到公众号草稿箱（publish=True 时继续正式发布）。

    record_id 由 API 层创建并传入；直接调用本任务（如重试）时可省略，
    此时在本任务内补建一条发布记录。

    注意：微信侧失败必须显式落到 job.error 与 publish_records.error。
    以前这里无论草稿是否创建成功都把 job 标成 SUCCESS，导致前端提示"已发送"，
    而公众号草稿箱里什么都没有，用户看不到任何失败原因。
    """
    t0 = time.perf_counter()
    await _set_job(job_id, start=True, progress=5)
    publisher = get_publisher()
    paper_id: str | None = None
    try:
        if not record_id:
            record_id = await _create_publish_record(article_id)

        async with async_session_factory() as session:
            art = await repositories.get_article(session, article_id)
            if not art:
                raise ValueError(f"文章不存在: {article_id}")
            paper_id = art.paper_id
            title = art.title or "未命名"
            content = art.content or ""
            images = list(art.images or [])
            digest = art.summary or ""
            author = getattr(art, "author", None) or "PaperHub"
            theme = getattr(art, "theme", None)
            cover_image = getattr(art, "cover_image", None)

        await _set_job(job_id, progress=20)
        image_map = await _upload_content_images(publisher, images)
        thumb_media_id = await _ensure_thumb_media_id(publisher, images, cover_image)
        payload = build_article_payload(
            title,
            content,
            image_map,
            thumb_media_id=thumb_media_id,
            author=author,
            digest=digest,
            theme=theme,
        )
        await _set_job(job_id, progress=45)

        draft = await publisher.create_draft(payload)
        if not draft.success:
            error = draft.error or "创建草稿失败"
            await _finish_publish_record(
                record_id, models.PublishStatus.FAILED, error=error
            )
            return await _publish_failed(job_id, error, article_id, paper_id, publisher, t0)

        external_id = draft.external_id
        error = None
        if publish:
            pub = await publisher.publish(external_id or "")
            external_id = pub.external_id or external_id
            if not pub.success:
                error = pub.error or "发布失败"
        await _set_job(job_id, progress=80)

        if error:
            await _finish_publish_record(
                record_id,
                models.PublishStatus.FAILED,
                external_id=external_id,
                error=error,
            )
            return await _publish_failed(job_id, error, article_id, paper_id, publisher, t0)

        await _finish_publish_record(
            record_id, models.PublishStatus.SUCCESS, external_id=external_id
        )
        await _set_article_status(
            article_id,
            models.ArticleStatus.PUBLISHED
            if publish
            else models.ArticleStatus.SENT_TO_PLATFORM,
        )
        await _set_job(job_id, progress=100, status=models.JobStatus.SUCCESS, finish=True)
        log_event(
            20,
            "task_done",
            paper_id=paper_id,
            job_id=job_id,
            task="publish_wechat",
            publish=publish,
            mock=publisher.is_mock(),
            duration=round(time.perf_counter() - t0, 3),
        )
        return {
            "article_id": article_id,
            "record_id": record_id,
            "status": "success",
            "external_id": external_id,
            "mock": publisher.is_mock(),
        }
    except Exception as e:  # noqa: BLE001
        error = str(e) or e.__class__.__name__
        await _finish_publish_record(record_id, models.PublishStatus.FAILED, error=error)
        return await _publish_failed(job_id, error, article_id, paper_id, publisher, t0)
