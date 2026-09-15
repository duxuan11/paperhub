"""自定义 Skill（DB）与内置 Skill（文件）的合并 / CRUD 测试 —— 无需数据库。"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app import models
from app.core.config import settings as app_settings
from app.core.database import get_session
from app.services import skill_registry
from app.services.skill import (
    Skill,
    list_skill_options,
    list_skills,
    load_skill,
)


def run(coro):
    return asyncio.run(coro)


CUSTOM_SUMMARY = Skill(
    name="paper-summary",
    description="自定义总结",
    prompt="CUSTOM",
    tools=["get_paper"],
    source="custom",
)


# ---------- 合并：自定义优先，且隐藏被覆盖的内置 ----------


def test_load_skill_prefers_custom_registry():
    registry = {"paper-summary": CUSTOM_SUMMARY}
    assert load_skill("paper-summary", registry=registry).prompt == "CUSTOM"
    builtin = load_skill("figure-analysis", registry=registry)
    assert builtin is not None and builtin.prompt != "CUSTOM"


def test_list_skills_marks_source_and_hides_overridden_builtin():
    rows = {s["name"]: s for s in list_skills(registry={"paper-summary": CUSTOM_SUMMARY})}
    assert rows["paper-summary"]["source"] == "custom"
    assert rows["paper-summary"]["is_builtin"] is False
    assert rows["figure-analysis"]["source"] == "builtin"
    assert rows["figure-analysis"]["is_builtin"] is True


def test_list_skill_options_exposes_prompt_and_override_flag():
    rows = {
        s["name"]: s
        for s in list_skill_options(registry={"paper-summary": CUSTOM_SUMMARY})
    }
    assert rows["paper-summary"]["prompt"] == "CUSTOM"
    assert rows["paper-summary"]["overrides_builtin"] is True
    assert rows["figure-analysis"]["overrides_builtin"] is False
    assert rows["figure-analysis"]["prompt"].strip()


# ---------- 名称校验 ----------


@pytest.mark.parametrize("name", ["my-skill", "skill2", "a", "a-b-c-1"])
def test_validate_name_accepts(name):
    assert skill_registry.validate_name(name) == name


@pytest.mark.parametrize(
    "name", ["", "A", "my skill", "../etc", "a" * 65, "-lead", "中文", "a/b"]
)
def test_validate_name_rejects(name):
    with pytest.raises(skill_registry.InvalidSkillName):
        skill_registry.validate_name(name)


# ---------- CRUD（FakeSession + 猴补仓储） ----------


class FakeSession:
    def __init__(self, store):
        self.store = store

    def add(self, obj):
        self.store[obj.name] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def delete(self, obj):
        self.store.pop(obj.name, None)


@pytest.fixture
def store(monkeypatch):
    data: dict[str, models.CustomSkill] = {}

    async def _list(session):
        return list(data.values())

    async def _get(session, name):
        return data.get(name)

    monkeypatch.setattr(skill_registry.repositories, "list_custom_skills", _list)
    monkeypatch.setattr(skill_registry.repositories, "get_custom_skill", _get)
    return data


@pytest.fixture
def session(store):
    return FakeSession(store)


def test_create_custom_skill(store, session):
    row = run(
        skill_registry.create_skill(
            session,
            name="my-skill",
            description="说明",
            tools=["get_paper"],
            prompt="P",
        )
    )
    assert row.name == "my-skill" and row.prompt == "P" and row.tools == ["get_paper"]
    assert store["my-skill"] is row


def test_create_overriding_builtin_is_allowed(store, session):
    row = run(
        skill_registry.create_skill(
            session, name="paper-summary", description="d", tools=[], prompt="OVERRIDE"
        )
    )
    assert row.prompt == "OVERRIDE"


def test_create_duplicate_raises(store, session):
    run(
        skill_registry.create_skill(
            session, name="my-skill", description="", tools=[], prompt="P"
        )
    )
    with pytest.raises(skill_registry.SkillAlreadyExists):
        run(
            skill_registry.create_skill(
                session, name="my-skill", description="", tools=[], prompt="P2"
            )
        )


def test_create_rejects_bad_name(store, session):
    with pytest.raises(skill_registry.InvalidSkillName):
        run(
            skill_registry.create_skill(
                session, name="Bad Name", description="", tools=[], prompt="P"
            )
        )


def test_update_custom_skill(store, session):
    run(
        skill_registry.create_skill(
            session, name="my-skill", description="", tools=[], prompt="P"
        )
    )
    row = run(
        skill_registry.update_skill(
            session, "my-skill", description="new", tools=["a"], prompt="P2"
        )
    )
    assert row.description == "new" and row.prompt == "P2" and row.tools == ["a"]


def test_update_missing_raises(store, session):
    with pytest.raises(skill_registry.SkillNotFound):
        run(
            skill_registry.update_skill(
                session, "ghost", description="", tools=[], prompt=""
            )
        )


def test_delete_custom_skill(store, session):
    run(
        skill_registry.create_skill(
            session, name="my-skill", description="", tools=[], prompt="P"
        )
    )
    run(skill_registry.delete_skill(session, "my-skill"))
    assert "my-skill" not in store


def test_delete_missing_raises(store, session):
    with pytest.raises(skill_registry.SkillNotFound):
        run(skill_registry.delete_skill(session, "ghost"))


# ---------- 读取详情（含内置，不依赖 DB 行） ----------


def test_get_detail_returns_builtin_without_db_row(store, session):
    detail = run(skill_registry.get_detail(session, "paper-summary"))
    assert detail is not None
    assert detail["is_builtin"] is True
    assert detail["prompt"].strip()
    assert detail["overrides_builtin"] is False


def test_get_detail_returns_custom_override(store, session):
    run(
        skill_registry.create_skill(
            session, name="paper-summary", description="d", tools=[], prompt="MINE"
        )
    )
    detail = run(skill_registry.get_detail(session, "paper-summary"))
    assert detail["prompt"] == "MINE"
    assert detail["is_builtin"] is False
    assert detail["overrides_builtin"] is True


def test_get_detail_missing_returns_none(store, session):
    assert run(skill_registry.get_detail(session, "no-such-skill")) is None


# ---------- 路由 ----------


def test_skills_routes_registered():
    from app.api.v1 import skills as api

    routes = {
        (route.path, method)
        for route in api.router.routes
        for method in (getattr(route, "methods", None) or [])
    }
    assert ("/api/v1/skills", "GET") in routes
    assert ("/api/v1/skills", "POST") in routes
    assert ("/api/v1/skills/{name}", "GET") in routes
    assert ("/api/v1/skills/{name}", "PUT") in routes
    assert ("/api/v1/skills/{name}", "DELETE") in routes


# ---------- REST API ----------


@pytest.fixture
def client(store, session, monkeypatch):
    from app.main import app

    monkeypatch.setattr(app_settings, "paperhub_api_key", "")
    app.dependency_overrides[get_session] = lambda: session
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_api_lists_builtin_and_custom(store, session, client):
    run(
        skill_registry.create_skill(
            session, name="my-skill", description="d", tools=[], prompt="P"
        )
    )
    resp = client.get("/api/v1/skills")
    assert resp.status_code == 200
    rows = {s["name"]: s for s in resp.json()["skills"]}
    assert rows["my-skill"]["source"] == "custom"
    assert rows["paper-summary"]["is_builtin"] is True
    assert rows["paper-summary"]["prompt"].strip()


def test_api_create_override_builtin(store, session, client):
    resp = client.post(
        "/api/v1/skills",
        json={"name": "paper-summary", "description": "d", "tools": [], "prompt": "MINE"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["prompt"] == "MINE"
    assert body["overrides_builtin"] is True
    assert body["is_builtin"] is False


def test_api_create_duplicate_conflict(store, session, client):
    assert client.post("/api/v1/skills", json={"name": "dup", "prompt": "P"}).status_code == 201
    assert client.post("/api/v1/skills", json={"name": "dup", "prompt": "P2"}).status_code == 409


def test_api_create_rejects_bad_name(store, session, client):
    resp = client.post("/api/v1/skills", json={"name": "Bad Name", "prompt": "P"})
    assert resp.status_code == 400


def test_api_update_and_delete_custom(store, session, client):
    client.post("/api/v1/skills", json={"name": "my-skill", "prompt": "P"})
    updated = client.put("/api/v1/skills/my-skill", json={"prompt": "P2"})
    assert updated.status_code == 200 and updated.json()["prompt"] == "P2"
    assert client.delete("/api/v1/skills/my-skill").status_code == 204
    assert client.get("/api/v1/skills/my-skill").status_code == 404


def test_api_update_and_delete_missing_404(store, session, client):
    assert client.put("/api/v1/skills/ghost", json={"prompt": "P"}).status_code == 404
    assert client.delete("/api/v1/skills/ghost").status_code == 404


def test_api_get_builtin_detail(store, session, client):
    resp = client.get("/api/v1/skills/paper-summary")
    assert resp.status_code == 200
    assert resp.json()["is_builtin"] is True
