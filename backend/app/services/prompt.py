"""AI 分析提示词配置（设置页可编辑，持久化在 app_settings 表）。

论文的「AI 分析」由两部分拼装而成：
1. Skill（skills/<name>/SKILL.md 的正文）—— 结构化的分析框架；
2. 用户自定义提示词 —— 在设置页编辑，作为额外系统要求注入，用于微调口吻、
   篇幅、语言、关注点等，不必改动仓库里的 Skill 文件。

未配置时回退到 DEFAULT_ANALYSIS_SKILL + 空自定义提示词，行为与改造前一致。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app import repositories
from app.core.logging import get_logger
from app.services.skill import list_skills, load_skill

log = get_logger("prompt")

ANALYSIS_PROMPT_KEY = "analysis_prompt"
ANALYSIS_SKILL_KEY = "analysis_skill"
DEFAULT_ANALYSIS_SKILL = "paper-summary"

# 设置页「恢复默认」用；也是未自定义时的分析要求。
DEFAULT_ANALYSIS_PROMPT = """请严格按照 Skill 规定的结构输出完整分析，不要省略条目。
要求：
- 先给出 3~5 句话的整体速览，再展开各部分。
- 每个结论都要能追溯到论文中的章节、Figure 编号或具体数据。
- 论文未提供的信息，明确写「论文未提供相关信息」，不要推测。
- 使用中文，术语首次出现时给出英文原文。"""


def default_analysis_prompt() -> str:
    return DEFAULT_ANALYSIS_PROMPT


def skill_options() -> list[dict]:
    """可供「AI 分析」调用的 Skill 列表（含正文，供编辑器载入）。"""
    out: list[dict] = []
    for meta in list_skills():
        name = meta.get("name") or ""
        skill = load_skill(name)
        if not skill:
            continue
        out.append(
            {
                "name": name,
                "description": meta.get("description") or "",
                "tools": meta.get("tools") or [],
                "prompt": skill.prompt,
            }
        )
    return out


def skill_exists(name: str) -> bool:
    return any(s["name"] == name for s in skill_options())


async def get_analysis_config(session: AsyncSession) -> dict:
    """读取当前生效的分析配置（含默认值，供前端渲染编辑器）。"""
    prompt = await repositories.get_setting(session, ANALYSIS_PROMPT_KEY) or ""
    skill = await repositories.get_setting(session, ANALYSIS_SKILL_KEY) or ""
    if not skill or not skill_exists(skill):
        skill = DEFAULT_ANALYSIS_SKILL
    return {
        "skill": skill,
        "prompt": prompt,
        "default_skill": DEFAULT_ANALYSIS_SKILL,
        "default_prompt": DEFAULT_ANALYSIS_PROMPT,
        "skills": skill_options(),
    }


async def save_analysis_config(
    session: AsyncSession, *, skill: str | None, prompt: str | None
) -> dict:
    """保存分析配置（prompt 传空串等价于清除，回退到默认）。"""
    if skill is not None:
        skill = skill.strip()
        if skill and not skill_exists(skill):
            raise ValueError(f"Skill 不存在: {skill}")
        await repositories.set_setting(session, ANALYSIS_SKILL_KEY, skill or None)
    if prompt is not None:
        await repositories.set_setting(
            session, ANALYSIS_PROMPT_KEY, prompt.strip() or None
        )
    return await get_analysis_config(session)


async def resolve_for_analysis(
    session: AsyncSession, skill: str | None
) -> tuple[str, str | None]:
    """解析一次分析实际使用的 (skill, 自定义提示词)。

    任务里显式传入的 skill 优先；否则用设置页保存的默认 Skill。
    """
    prompt = await repositories.get_setting(session, ANALYSIS_PROMPT_KEY) or ""
    if not skill:
        skill = await repositories.get_setting(session, ANALYSIS_SKILL_KEY) or ""
    if not skill or not skill_exists(skill):
        skill = DEFAULT_ANALYSIS_SKILL
    return skill, (prompt.strip() or None)
