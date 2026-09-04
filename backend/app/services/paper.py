"""论文编排服务：上传、存储、解析结果落盘。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app import models
from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.core.minio import storage
from app.services.mineru import ParseResult

log = get_logger("paper")


def paper_local_dir(paper_id: str) -> Path:
    return settings.data_path / "papers" / paper_id


def _mirror(key: str, data: bytes) -> None:
    """写入本地镜像目录，便于调试与直接查看。"""
    p = settings.data_path / "minio" / key
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


async def create_paper_from_upload(
    session: AsyncSession, filename: str, data: bytes
) -> models.Paper:
    paper = models.Paper(filename=filename, status=models.PaperStatus.UPLOADED)
    session.add(paper)
    await session.flush()  # 生成 id
    key = f"{paper.id}/original.pdf"
    storage.put_bytes(key, data, "application/pdf")
    _mirror(key, data)
    paper.pdf_path = key
    await session.commit()
    await session.refresh(paper)
    log_event(
        logging.INFO, "paper_created", paper_id=paper.id, status=paper.status.value
    )
    return paper


async def store_parse_result(
    session: AsyncSession, paper_id: str, result: ParseResult
) -> None:
    paper = await session.get(models.Paper, paper_id)
    if not paper:
        raise ValueError(f"paper not found: {paper_id}")

    md_key = f"{paper_id}/markdown/paper.md"
    storage.put_bytes(md_key, result.markdown.encode("utf-8"), "text/markdown")
    _mirror(md_key, result.markdown.encode("utf-8"))

    image_keys: list[str] = []
    for img in result.images:
        img_key = f"{paper_id}/images/{img.name}"
        storage.put_bytes(img_key, img.data, "image/png")
        _mirror(img_key, img.data)
        image_keys.append(img_key)

    result.metadata["markdown_key"] = md_key
    result.metadata["images"] = image_keys
    result.metadata["source"] = result.source
    meta_key = f"{paper_id}/metadata.json"
    meta_bytes = json.dumps(result.metadata, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )
    storage.put_bytes(meta_key, meta_bytes, "application/json")
    _mirror(meta_key, meta_bytes)

    paper.markdown_path = md_key
    paper.metadata_path = meta_key
    paper.status = models.PaperStatus.PARSED
    paper.title = paper.title or _guess_title(result.markdown)
    paper.abstract = paper.abstract or _guess_abstract(result.markdown)
    await session.commit()


async def mark_figure_detecting(session: AsyncSession, paper_id: str) -> None:
    paper = await session.get(models.Paper, paper_id)
    if paper:
        paper.status = models.PaperStatus.FIGURE_DETECTING
        await session.commit()


async def add_figures(session: AsyncSession, paper_id: str, figures: list) -> None:
    paper = await session.get(models.Paper, paper_id)
    if not paper:
        return
    # 重新检测时先清空旧记录，避免重复
    await session.execute(
        delete(models.Figure).where(models.Figure.paper_id == paper_id)
    )
    for i, f in enumerate(figures, start=1):
        session.add(
            models.Figure(
                paper_id=paper_id,
                figure_number=f.get("figure_number", i),
                image_path=f["image_path"],
                caption=f.get("caption"),
                bbox=f.get("bbox"),
                type=f.get("type", "figure"),
                page=f.get("page"),
            )
        )
    paper.status = models.PaperStatus.READY
    await session.commit()


def _guess_title(md: str) -> str | None:
    for ln in md.splitlines():
        if ln.startswith("# "):
            return ln[2:].strip()[:512]
    return None


def _guess_abstract(md: str) -> str | None:
    m = re.search(r"(?i)abstract[\s\S]{0,80}?\n(.*?)(?=\n#|\n\n##)", md)
    if m:
        return m.group(1).strip()[:2000]
    return None
