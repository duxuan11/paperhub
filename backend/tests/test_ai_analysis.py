"""AI 分析（Skills + Model + Prompt 配置与执行）单元测试 —— 无需数据库/Redis。"""

import asyncio

import pytest

from app import models
from app.services import analysis as service
from app.services.analysis import AnalysisPlan, MineruNotReadyError


def run(coro):
    return asyncio.run(coro)


AVAILABLE = [
    "paper-summary",
    "figure-analysis",
    "paper-method-analysis",
    "wechat-article",
]


def _plan(**kw):
    base = {
        "available": AVAILABLE,
        "default_skill": "paper-summary",
        "default_model": "deepseek-chat",
    }
    base.update(kw)
    return service.resolve_plan(**base)


# ---------- resolve_plan：论文级配置 > 全局默认 > 内置默认 ----------


def test_resolve_plan_uses_selected_skills_in_order_and_dedupes():
    plan = _plan(selected_skills=["figure-analysis", "paper-summary", "figure-analysis"])
    assert plan.skills == ["figure-analysis", "paper-summary"]


def test_resolve_plan_filters_unknown_skills():
    plan = _plan(selected_skills=["__nope__", "paper-summary"])
    assert plan.skills == ["paper-summary"]


def test_resolve_plan_falls_back_when_all_selected_skills_unknown():
    plan = _plan(selected_skills=["__nope__"], fallback_skill="figure-analysis")
    assert plan.skills == ["figure-analysis"]


def test_resolve_plan_falls_back_to_builtin_default_when_nothing_usable():
    assert _plan().skills == ["paper-summary"]
    assert _plan(fallback_skill="__nope__").skills == ["paper-summary"]


def test_resolve_plan_model_prefers_config_then_default():
    assert _plan(model="deepseek-reasoner").model == "deepseek-reasoner"
    assert _plan(model="   ").model == "deepseek-chat"


def test_resolve_plan_prompt_prefers_config_then_fallback():
    assert _plan(custom_prompt="  用一句话 ").custom_prompt == "用一句话"
    assert _plan(fallback_prompt="全局提示").custom_prompt == "全局提示"
    assert _plan().custom_prompt is None


def test_resolve_plan_for_paper_explicit_skill_wins(monkeypatch):
    async def fake_config(session, paper_id):
        return models.AIAnalysisConfig(
            paper_id=paper_id,
            enabled=True,
            selected_skills=["figure-analysis"],
        )

    monkeypatch.setattr(service, "get_config", fake_config)
    monkeypatch.setattr(
        service.prompt_service,
        "skill_options",
        lambda: [{"name": "paper-summary"}, {"name": "figure-analysis"}],
    )
    plan = run(
        service.resolve_plan_for_paper(None, "p1", explicit_skill="paper-summary")
    )
    assert plan.skills == ["paper-summary"]


def test_resolve_plan_for_paper_uses_saved_selection_without_explicit(monkeypatch):
    async def fake_config(session, paper_id):
        return models.AIAnalysisConfig(
            paper_id=paper_id,
            enabled=True,
            selected_skills=["figure-analysis"],
            model="deepseek-reasoner",
        )

    monkeypatch.setattr(service, "get_config", fake_config)
    monkeypatch.setattr(
        service.prompt_service,
        "skill_options",
        lambda: [{"name": "paper-summary"}, {"name": "figure-analysis"}],
    )
    plan = run(service.resolve_plan_for_paper(None, "p1"))
    assert plan.skills == ["figure-analysis"]
    assert plan.model == "deepseek-reasoner"


# ---------- MinerU 前置检查 ----------


class _Paper:
    def __init__(self, markdown_path: str | None = None):
        self.markdown_path = markdown_path
        self.analysis = None
        self.analysis_path = None
        self.status = None


def test_ensure_parsed_raises_when_mineru_not_ready():
    with pytest.raises(MineruNotReadyError) as exc:
        service.ensure_parsed(_Paper())
    assert "MinerU" in str(exc.value)


def test_ensure_parsed_raises_when_paper_missing():
    with pytest.raises(MineruNotReadyError):
        service.ensure_parsed(None)


def test_ensure_parsed_passes_when_markdown_ready():
    service.ensure_parsed(_Paper("p1/markdown.md"))


# ---------- 汇总 ----------


def test_combine_results_keeps_skill_order_and_content():
    text = service.combine_results(
        [("paper-summary", "A"), ("figure-analysis", "B")]
    )
    assert "paper-summary" in text and "A" in text
    assert "figure-analysis" in text and "B" in text
    assert text.index("paper-summary") < text.index("figure-analysis")


def test_combine_results_empty():
    assert service.combine_results([]) == ""


# ---------- run_analysis：逐 Skill 独立调用 + 落库 ----------


class FakeSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def get(self, model, key):
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        return None


def test_run_analysis_rejects_when_mineru_not_ready(monkeypatch):
    async def fake_get_paper(session, paper_id):
        return _Paper()

    monkeypatch.setattr(service.repositories, "get_paper", fake_get_paper)
    with pytest.raises(MineruNotReadyError):
        run(
            service.run_analysis(
                FakeSession(), "p1", AnalysisPlan(["paper-summary"], "m", None)
            )
        )


def test_run_analysis_calls_llm_once_per_skill_and_saves_results(monkeypatch):
    calls: list[tuple[str, str | None]] = []
    saved: dict[str, models.AIAnalysisResult] = {}

    async def fake_get_paper(session, paper_id):
        return _Paper("p1/markdown.md")

    async def fake_upsert(session, paper_id, skill, content, model=None):
        row = models.AIAnalysisResult(
            paper_id=paper_id, skill=skill, content=content, model=model
        )
        saved[skill] = row
        return row

    async def fake_build_messages(session, message, **kw):
        return [
            {"role": "system", "content": kw.get("skill_name")},
            {"role": "user", "content": message},
        ]

    class FakeLLM:
        async def complete(self, messages, **kw):
            calls.append((messages[0]["content"], kw.get("model")))
            return f"分析-{messages[0]['content']}"

    monkeypatch.setattr(service.repositories, "get_paper", fake_get_paper)
    monkeypatch.setattr(service.repositories, "upsert_analysis_result", fake_upsert)
    monkeypatch.setattr(service.chat, "build_messages", fake_build_messages)
    monkeypatch.setattr(service, "get_llm_service", lambda: FakeLLM())
    puts: list[str] = []
    monkeypatch.setattr(
        service.storage, "put_bytes", lambda key, data, ctype=None: puts.append(key)
    )

    session = FakeSession()
    plan = AnalysisPlan(
        skills=["paper-summary", "figure-analysis"],
        model="deepseek-reasoner",
        custom_prompt="精简",
    )
    results = run(service.run_analysis(session, "p1", plan))

    assert [r.skill for r in results] == ["paper-summary", "figure-analysis"]
    assert [name for name, _ in calls] == ["paper-summary", "figure-analysis"]
    assert all(model == "deepseek-reasoner" for _, model in calls)
    assert saved["paper-summary"].content == "分析-paper-summary"
    assert puts == ["p1/analysis.md"]


# ---------- 配置仓储（回归：get_setting/set_setting 曾丢失） ----------


class SettingSession:
    def __init__(self):
        self.rows: dict[str, models.AppSetting] = {}

    async def get(self, model, key):
        return self.rows.get(key)

    def add(self, obj):
        self.rows[obj.key] = obj

    async def commit(self):
        pass


def test_repositories_setting_roundtrip():
    from app import repositories

    session = SettingSession()
    run(repositories.set_setting(session, "k", "v"))
    assert run(repositories.get_setting(session, "k")) == "v"
    run(repositories.set_setting(session, "k", None))
    assert run(repositories.get_setting(session, "k")) is None


class ResultSession(FakeSession):
    def __init__(self):
        super().__init__()
        self.rows: dict[tuple[str, str], models.AIAnalysisResult] = {}

    async def get(self, model, key):
        return self.rows.get(key)

    def add(self, obj):
        self.rows[(obj.paper_id, obj.skill)] = obj


def test_repositories_upsert_analysis_result_overwrites_same_skill():
    from app import repositories

    session = ResultSession()
    first = run(
        repositories.upsert_analysis_result(session, "p1", "paper-summary", "v1", "m1")
    )
    second = run(
        repositories.upsert_analysis_result(session, "p1", "paper-summary", "v2", "m2")
    )
    assert first is second
    assert second.content == "v2" and second.model == "m2"
    assert len(session.rows) == 1


# ---------- Schema / 路由 ----------


def test_ai_analysis_schemas_accept_partial_update():
    from app.schemas import AIAnalysisConfigOut, AIAnalysisConfigUpdate

    upd = AIAnalysisConfigUpdate()
    assert upd.enabled is None and upd.selected_skills is None
    upd2 = AIAnalysisConfigUpdate(
        enabled=False, model="deepseek-chat", selected_skills=["paper-summary"]
    )
    assert upd2.enabled is False
    assert upd2.selected_skills == ["paper-summary"]

    out = AIAnalysisConfigOut(paper_id="p1", selected_skills=["paper-summary"])
    assert out.enabled is True
    assert out.model == ""
    assert out.custom_prompt == ""


def test_ai_analysis_routes_registered():
    from app.api.v1 import analysis as api

    routes = {
        (route.path, method)
        for route in api.router.routes
        for method in (getattr(route, "methods", None) or [])
    }
    assert ("/api/v1/papers/{paper_id}/ai-analysis", "GET") in routes
    assert ("/api/v1/papers/{paper_id}/ai-analysis/config", "PUT") in routes
    assert ("/api/v1/papers/{paper_id}/ai-analysis/run", "POST") in routes


# ---------- 公众号文章优先使用 AI 分析结果 ----------


def test_article_source_includes_ai_analysis_when_available():
    from app.services.article import _build_source

    source = _build_source(
        "论文A",
        "# 论文A\n正文",
        "- Figure 1: x",
        analysis_text="## paper-summary\n\n核心结论",
    )
    assert "<ai_analysis>" in source
    assert "核心结论" in source
    assert "<paper_markdown>" in source
    assert source.index("<ai_analysis>") < source.index("<paper_markdown>")


def test_article_source_falls_back_to_markdown_only():
    from app.services.article import _build_source

    source = _build_source("论文A", "# 论文A\n正文", "", analysis_text="")
    assert "<ai_analysis>" not in source
    assert "<paper_markdown>" in source
