"""公众号文章生成服务。"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories
from app.core.logging import get_logger
from app.core.minio import storage
from app.services.chat import BASE_SYSTEM
from app.services.llm import get_llm_service
from app.services.skill import load_skill

log = get_logger("article")

STYLES = ["科研论文解读", "科研前沿", "一文读懂", "方法解析", "论文精读"]

STYLE_GUIDE = {
    "科研论文解读": "偏学术解读，突出研究背景、科学问题、创新点、方法与结果，语气专业但易读。",
    "科研前沿": "突出该论文在领域中的前沿性与突破意义，强调与已有工作的区别。",
    "一文读懂": "面向大众科普向，语言通俗，多用类比，突出核心思想。",
    "方法解析": "重点解析技术路线与实验方法，适合方法学读者。",
    "论文精读": "逐节精读，结构完整，包含背景、方法、结果、讨论、局限与启发。",
}


def _extract_title(md: str, fallback: str) -> str:
    for ln in md.splitlines():
        if ln.startswith("# "):
            t = ln[2:].strip()
            if t:
                return t[:128]
    return fallback


def _extract_summary(md: str) -> str | None:
    for ln in md.splitlines():
        s = ln.strip()
        if s.startswith(">"):
            return s.lstrip(">").strip()[:1000]
    # 取正文第一段
    for ln in md.splitlines():
        s = ln.strip()
        if s and not s.startswith("#") and len(s) > 10:
            return s[:1000]
    return None


def _extract_references(md: str) -> list[str]:
    refs: list[str] = []
    in_ref = False
    for ln in md.splitlines():
        s = ln.strip()
        if re.match(r"^#{1,3}\s*(参考文献|References|参考)", s, re.I):
            in_ref = True
            continue
        if in_ref and re.match(r"^\[?\d+\]?\.?\s+\S", s):
            refs.append(s)
        elif in_ref and s.startswith("#"):
            break
    return refs[:20]


async def generate_article(
    session: AsyncSession,
    paper_id: str,
    *,
    skill_name: str = "wechat-article",
    style: str = "科研论文解读",
    extra_instructions: str | None = None,
) -> models.Article:
    paper = await repositories.get_paper(session, paper_id)
    if not paper:
        raise ValueError(f"paper not found: {paper_id}")

    md_text = ""
    if paper.markdown_path:
        data = storage.get_bytes(paper.markdown_path)
        if data:
            md_text = data.decode("utf-8", errors="ignore")

    figures = await repositories.list_figures(session, paper_id)
    fig_lines = "\n".join(
        f"- Figure {f.figure_number}: {f.caption or '（无标题）'}" for f in figures
    )

    skill = load_skill(skill_name) or load_skill("wechat-article")
    system = (
        BASE_SYSTEM
        + "\n\n请按照以下 Skill 要求生成微信公众号文章：\n"
        + (skill.prompt if skill else "")
    )
    system += f"\n\n要求的文章风格：{style} —— {STYLE_GUIDE.get(style, '')}"
    if extra_instructions:
        system += f"\n额外要求：{extra_instructions}"

    user = (
        f"论文标题：{paper.title or paper.filename or '未命名'}\n\n"
        f"论文 Markdown：\n<paper_markdown>\n{md_text[:40000]}\n</paper_markdown>\n\n"
        f"论文中的 Figure 列表：\n<figures>\n{fig_lines or '无'}\n</figures>\n\n"
        f"请生成完整的微信公众号文章（Markdown 格式），必须包含：# 标题、> 导语、正文（多级标题）、"
        f"关键图示（用 ![]({{{{figure:N}}}} 占位，N 从 0 开始）、论文来源、参考文献。"
    )

    llm = get_llm_service()
    content = await llm.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    )

    title = _extract_title(content, f"{paper.title or paper.filename}｜{style}")
    summary = _extract_summary(content)
    references = _extract_references(content)

    article = models.Article(
        paper_id=paper_id,
        title=title,
        summary=summary,
        content=content,
        style=style,
        skill=skill_name,
        references=references,
        images=[f.image_path for f in figures],
        status=models.ArticleStatus.GENERATED,
    )
    session.add(article)
    if paper.status in (models.PaperStatus.READY, models.PaperStatus.ANALYZED):
        paper.status = models.PaperStatus.CONTENT_GENERATED
    await session.commit()
    await session.refresh(article)
    return article
