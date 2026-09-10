"""AI 分析提示词配置（设置页编辑器）相关单元测试 —— 无需数据库/Redis。"""

import asyncio

from app.services.chat import build_messages
from app.services.prompt import (
    DEFAULT_ANALYSIS_PROMPT,
    DEFAULT_ANALYSIS_SKILL,
    default_analysis_prompt,
    skill_exists,
    skill_options,
)


def run(coro):
    return asyncio.run(coro)


def test_skill_options_expose_prompt_body():
    opts = skill_options()
    names = [s["name"] for s in opts]
    assert DEFAULT_ANALYSIS_SKILL in names
    summary = next(s for s in opts if s["name"] == DEFAULT_ANALYSIS_SKILL)
    # 编辑器要把 Skill 正文载入文本框，因此 prompt 必须非空
    assert summary["prompt"].strip()
    assert summary["tools"]
    assert summary["description"]


def test_skill_exists():
    assert skill_exists(DEFAULT_ANALYSIS_SKILL)
    assert not skill_exists("__不存在的技能__")


def test_default_prompt_is_non_empty():
    assert default_analysis_prompt() == DEFAULT_ANALYSIS_PROMPT
    assert len(DEFAULT_ANALYSIS_PROMPT.strip()) > 20


def test_build_messages_injects_custom_prompt():
    msgs = run(
        build_messages(
            None,  # 无 paper_id 时不触碰数据库
            "开始分析",
            skill_name=DEFAULT_ANALYSIS_SKILL,
            extra_system="只用一句话总结，不要列条目。",
        )
    )
    system = msgs[0]["content"]
    assert msgs[0]["role"] == "system"
    assert "请遵循以下 Skill 要求" in system
    assert "用户自定义要求" in system
    assert "只用一句话总结，不要列条目。" in system
    assert msgs[-1] == {"role": "user", "content": "开始分析"}


def test_build_messages_without_custom_prompt_keeps_old_behaviour():
    msgs = run(build_messages(None, "开始分析", skill_name=DEFAULT_ANALYSIS_SKILL))
    assert "用户自定义要求" not in msgs[0]["content"]
    assert "请遵循以下 Skill 要求" in msgs[0]["content"]


def test_build_messages_ignores_blank_custom_prompt():
    msgs = run(build_messages(None, "开始分析", skill_name=None, extra_system="   \n  "))
    assert "用户自定义要求" not in msgs[0]["content"]


def test_analysis_prompt_schemas_accept_partial_update():
    from app.schemas import AnalysisPromptOut, AnalysisPromptUpdate, SkillDetail

    upd = AnalysisPromptUpdate()
    assert upd.skill is None and upd.prompt is None
    upd2 = AnalysisPromptUpdate(prompt="改一下口吻")
    assert upd2.skill is None and upd2.prompt == "改一下口吻"

    out = AnalysisPromptOut(
        skill="paper-summary",
        prompt="",
        default_skill="paper-summary",
        default_prompt=DEFAULT_ANALYSIS_PROMPT,
        skills=[SkillDetail(name="paper-summary", prompt="x")],
    )
    assert out.skills[0].name == "paper-summary"
    assert out.skills[0].prompt == "x"


def test_analyze_task_accepts_empty_skill():
    """analyze 任务签名应允许空 skill（由设置页保存的默认 Skill 兜底）。"""
    import inspect

    from app.workers.tasks import analyze_paper

    sig = inspect.signature(analyze_paper)
    assert sig.parameters["skill"].default == ""


def test_settings_analysis_prompt_routes_registered():
    from app.api.v1 import misc

    routes = {
        (getattr(r, "path", ""), method)
        for r in misc.router.routes
        for method in (getattr(r, "methods", None) or [])
    }
    assert ("/api/v1/settings/analysis-prompt", "GET") in routes
    assert ("/api/v1/settings/analysis-prompt", "PUT") in routes
    assert ("/api/v1/settings/skills", "GET") in routes
