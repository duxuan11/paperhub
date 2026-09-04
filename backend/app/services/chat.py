"""Chat 服务：构建论文上下文 + Skill + 流式回复。"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories
from app.core.minio import storage
from app.services.llm import get_llm_service
from app.services.skill import load_skill

BASE_SYSTEM = (
    "你是 PaperHub 的科研论文分析助手。你基于用户提供的论文 Markdown 内容回答问题，"
    "用中文回答，条理清晰、引用论文中的具体章节和 Figure。"
    "严禁编造论文中不存在的数据；论文未提供的信息请明确说明“论文未提供相关信息”。"
)


def _figures_block(figures: list[models.Figure]) -> str:
    lines = []
    for f in figures:
        lines.append(
            f"- Figure {f.figure_number}: type={f.type}, caption={f.caption or '（无标题）'}, image_path={f.image_path}"
        )
    return "\n".join(lines)


async def build_messages(
    session: AsyncSession,
    message: str,
    *,
    paper_id: str | None = None,
    skill_name: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": BASE_SYSTEM}]

    paper_ctx = ""
    if paper_id:
        paper = await repositories.get_paper(session, paper_id)
        if paper and paper.markdown_path:
            md = storage.get_bytes(paper.markdown_path)
            if md:
                md_text = md.decode("utf-8", errors="ignore")
                paper_ctx += f"<paper_markdown>\n{md_text[:40000]}\n</paper_markdown>\n"
            figures = await repositories.list_figures(session, paper_id)
            if figures:
                paper_ctx += "<figures>\n" + _figures_block(figures) + "\n</figures>\n"
            if paper.title:
                paper_ctx = f"<paper_title>{paper.title}</paper_title>\n" + paper_ctx
        if paper and not paper.markdown_path:
            paper_ctx += "该论文尚未解析完成，无 Markdown 内容。\n"

    if paper_ctx:
        messages[0]["content"] += "\n\n当前论文上下文：\n" + paper_ctx

    if skill_name:
        skill = load_skill(skill_name)
        if skill:
            messages[0]["content"] += "\n\n请遵循以下 Skill 要求：\n" + skill.prompt

    for h in (history or [])[-10:]:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})
    return messages


async def stream_chat(
    session: AsyncSession,
    message: str,
    *,
    paper_id: str | None = None,
    skill_name: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    messages = await build_messages(
        session, message, paper_id=paper_id, skill_name=skill_name, history=history
    )
    llm = get_llm_service()
    async for delta in llm.stream_complete(messages):
        yield delta
