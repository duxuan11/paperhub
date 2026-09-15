"""AI 分析：按用户配置的 Skills 对 MinerU 解析结果执行结构化分析。

流程严格建立在 MinerU 之上，不重新读取 PDF：

    MinerU Markdown + Figures
        -> 逐个 Skill 组装 Prompt（System + Skill + 自定义要求 + 论文内容）
        -> 调用 LLM（可用论文级 model 覆盖）
        -> 每个 Skill 落一条 AIAnalysisResult
        -> 汇总写入 Paper.analysis（兼容旧接口 / 公众号生成）

设计要点：
- 逐个 Skill 单独调用，避免把所有内容塞进一个巨大 Prompt；
- 论文级配置（selected_skills/model/custom_prompt）优先，缺省回退到设置页的
  全局默认，再回退到内置默认，保证旧流程行为不变。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories
from app.core.config import settings
from app.core.logging import get_logger
from app.core.minio import storage
from app.services import chat
from app.services import prompt as prompt_service
from app.services import skill_registry
from app.services.llm import get_llm_service

log = get_logger("analysis")

DEFAULT_ANALYSIS_SKILL = prompt_service.DEFAULT_ANALYSIS_SKILL
MINERU_NOT_READY_MESSAGE = "MinerU 解析尚未完成，暂时无法进行 AI 分析。"


class MineruNotReadyError(RuntimeError):
    """MinerU 尚未产出 Markdown 时拒绝执行 AI 分析。"""


@dataclass(frozen=True)
class AnalysisPlan:
    """一次 AI 分析实际执行的计划。"""

    skills: list[str] = field(default_factory=list)
    model: str = ""
    custom_prompt: str | None = None


def resolve_plan(
    *,
    selected_skills: list[str] | None = None,
    model: str | None = None,
    custom_prompt: str | None = None,
    fallback_skill: str | None = None,
    fallback_prompt: str | None = None,
    available: list[str] | None = None,
    default_skill: str = DEFAULT_ANALYSIS_SKILL,
    default_model: str = "",
) -> AnalysisPlan:
    """解析优先级：论文级配置 > 设置页全局默认 > 内置默认。

    ``available`` 为可用的 Skill ID 列表，用于过滤不存在/已删除的 Skill；
    传 ``None`` 时不做过滤（便于纯逻辑测试）。
    """
    allowed = set(available) if available is not None else None

    def _ok(name: str | None) -> bool:
        return bool(name) and (allowed is None or name in allowed)

    skills: list[str] = []
    for raw in selected_skills or []:
        name = (raw or "").strip()
        if name and _ok(name) and name not in skills:
            skills.append(name)

    if not skills:
        fallback = (fallback_skill or "").strip()
        skills = [fallback] if _ok(fallback) else [default_skill]

    prompt = (custom_prompt or "").strip() or (fallback_prompt or "").strip() or None
    return AnalysisPlan(
        skills=skills,
        model=(model or "").strip() or default_model,
        custom_prompt=prompt,
    )


def ensure_parsed(paper: models.Paper | None) -> None:
    """校验 MinerU 是否已产出 Markdown，否则拒绝分析。"""
    if paper is None or not paper.markdown_path:
        raise MineruNotReadyError(MINERU_NOT_READY_MESSAGE)


def combine_results(sections: list[tuple[str, str]]) -> str:
    """把各 Skill 结果拼成一份 Markdown（用于 Paper.analysis 汇总）。"""
    blocks = [
        f"## {skill}\n\n{(content or '').strip()}"
        for skill, content in sections
        if (content or "").strip()
    ]
    return "\n\n".join(blocks)


async def get_config(
    session: AsyncSession, paper_id: str
) -> models.AIAnalysisConfig | None:
    return await repositories.get_ai_analysis_config(session, paper_id)


async def save_config(
    session: AsyncSession,
    paper_id: str,
    *,
    enabled: bool | None = None,
    model: str | None = None,
    selected_skills: list[str] | None = None,
    custom_prompt: str | None = None,
) -> models.AIAnalysisConfig:
    return await repositories.upsert_ai_analysis_config(
        session,
        paper_id,
        enabled=enabled,
        model=model,
        selected_skills=selected_skills,
        custom_prompt=custom_prompt,
    )


async def resolve_plan_for_paper(
    session: AsyncSession,
    paper_id: str,
    *,
    fallback_skill: str | None = None,
    fallback_prompt: str | None = None,
    explicit_skill: str | None = None,
) -> AnalysisPlan:
    """结合论文级配置与设置页全局默认，得出实际执行计划。

    ``explicit_skill``（旧接口显式指定的单个 Skill）优先级最高。
    """
    config = await get_config(session, paper_id)
    if explicit_skill:
        selected: list[str] | None = [explicit_skill]
    else:
        selected = list(config.selected_skills or []) if config else None
    available = await skill_registry.list_options(session)
    return resolve_plan(
        selected_skills=selected,
        model=config.model if config else None,
        custom_prompt=config.custom_prompt if config else None,
        fallback_skill=fallback_skill,
        fallback_prompt=fallback_prompt,
        available=[s["name"] for s in available],
        default_skill=prompt_service.DEFAULT_ANALYSIS_SKILL,
        default_model=settings.openai_model,
    )


async def run_analysis(
    session: AsyncSession, paper_id: str, plan: AnalysisPlan
) -> list[models.AIAnalysisResult]:
    """逐 Skill 执行分析并保存结果，同时汇总到 Paper.analysis。"""
    paper = await repositories.get_paper(session, paper_id)
    ensure_parsed(paper)

    llm = get_llm_service()
    registry = await skill_registry.load_registry(session)
    results: list[models.AIAnalysisResult] = []
    for skill in plan.skills:
        messages = await chat.build_messages(
            session,
            "请按照 Skill 要求完成这篇论文的对应分析。",
            paper_id=paper_id,
            skill_name=skill,
            extra_system=plan.custom_prompt,
            registry=registry,
        )
        kwargs = {"model": plan.model} if plan.model else {}
        content = await llm.complete(messages, **kwargs)
        row = await repositories.upsert_analysis_result(
            session, paper_id, skill, content, plan.model or None
        )
        results.append(row)

    summary = combine_results([(r.skill, r.content or "") for r in results])
    paper.analysis = summary
    paper.analysis_path = f"{paper_id}/analysis.md"
    storage.put_bytes(paper.analysis_path, summary.encode("utf-8"), "text/markdown")
    paper.status = models.PaperStatus.ANALYZED
    await session.commit()

    log.info(
        "ai_analysis_done paper=%s skills=%s model=%s",
        paper_id,
        ",".join(plan.skills),
        plan.model or "(default)",
    )
    return results
