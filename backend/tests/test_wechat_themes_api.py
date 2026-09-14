"""微信公众号主题 CRUD / 复制 / 设为默认 的服务层与 API 测试（无需数据库）。

用 ``FakeSession`` + 猴补仓储函数模拟 ``wechat_article_themes`` 表，
从而在无 PostgreSQL / Redis 的环境下验证：
- 创建 / 更新 / 删除 / 复制 / 设为默认；
- 内置主题（is_builtin）不可编辑、不可删除；
- 删除默认主题后自动回退到内置默认主题；
- 启动 seed 幂等；
- REST API 的状态码与鉴权行为。
"""

import asyncio

import pytest
from app import models, repositories
from app.core.config import settings as app_settings  # noqa: F401  —— 注册仓库根目录到 sys.path
from app.core.database import get_session
from app.services import wechat_theme as service
from fastapi.testclient import TestClient

from publishers.wechat.themes import BUILTIN_THEMES, DEFAULT_THEME_ID, get_theme


def run(coro):
    return asyncio.run(coro)


class FakeSession:
    """只实现主题服务用到的方法：add / commit / refresh / delete。"""

    def __init__(self, store: dict):
        self.store = store

    def add(self, obj):
        self.store[obj.id] = obj

    async def commit(self):
        return None

    async def refresh(self, obj):
        return None

    async def rollback(self):
        return None

    async def delete(self, obj):
        self.store.pop(obj.id, None)


@pytest.fixture
def store(monkeypatch):
    data: dict[str, models.WeChatArticleTheme] = {}

    async def _list(session):
        return list(data.values())

    async def _get(session, theme_id):
        return data.get(theme_id)

    monkeypatch.setattr(repositories, "list_wechat_themes", _list)
    monkeypatch.setattr(repositories, "get_wechat_theme", _get)
    return data


@pytest.fixture
def session(store):
    return FakeSession(store)


def builtin_row(theme_id: str = DEFAULT_THEME_ID, *, is_default: bool = True):
    theme = get_theme(theme_id)
    return models.WeChatArticleTheme(
        id=theme.id,
        name=theme.name,
        description=theme.description,
        config=theme.config,
        is_builtin=True,
        is_default=is_default,
    )


# ---------- 服务层 ----------


def test_create_theme_merges_defaults(store, session):
    row = run(
        service.create_theme(
            session, name="  我的主题  ", config={"colors": {"primary": "#FF0000"}}
        )
    )
    assert row.name == "我的主题"
    assert row.is_builtin is False and row.is_default is False
    assert row.config["colors"]["primary"] == "#FF0000"
    # 未提供的设计变量被补全，保证编译结果完整
    assert row.config["typography"]["bodySize"]
    assert store[row.id] is row


def test_create_default_clears_previous(store, session):
    existing = builtin_row(is_default=True)
    store[existing.id] = existing
    new = run(service.create_theme(session, name="新默认", is_default=True))
    assert new.is_default is True
    assert existing.is_default is False


def test_update_custom_theme(store, session):
    builtin = builtin_row()
    store[builtin.id] = builtin
    row = run(service.create_theme(session, name="A"))
    updated = run(
        service.update_theme(
            session,
            row.id,
            name="B",
            description="说明",
            config={"colors": {"primary": "#00FF00"}},
        )
    )
    assert updated.name == "B"
    assert updated.description == "说明"
    assert updated.config["colors"]["primary"] == "#00FF00"


def test_update_builtin_is_forbidden(store, session):
    row = builtin_row()
    store[row.id] = row
    with pytest.raises(service.BuiltinThemeImmutable):
        run(service.update_theme(session, row.id, name="hack"))


def test_update_missing_theme_raises(store, session):
    with pytest.raises(service.WeChatThemeNotFound):
        run(service.update_theme(session, "ghost", name="x"))


def test_delete_builtin_is_forbidden(store, session):
    row = builtin_row()
    store[row.id] = row
    with pytest.raises(service.BuiltinThemeImmutable):
        run(service.delete_theme(session, row.id))


def test_delete_custom_falls_back_to_builtin_default(store, session):
    default_builtin = builtin_row(is_default=True)
    store[default_builtin.id] = default_builtin
    custom = run(service.create_theme(session, name="C", is_default=True))
    assert default_builtin.is_default is False

    run(service.delete_theme(session, custom.id))
    assert custom.id not in store
    assert default_builtin.is_default is True


def test_duplicate_creates_custom_copy(store, session):
    src = builtin_row()
    store[src.id] = src
    dup = run(service.duplicate_theme(session, src.id))
    assert dup.id != src.id
    assert dup.is_builtin is False and dup.is_default is False
    assert dup.name.endswith("（副本）")
    assert dup.config == src.config


def test_set_default_keeps_single_default(store, session):
    first = builtin_row(DEFAULT_THEME_ID, is_default=True)
    second = builtin_row("paperhub-minimal", is_default=False)
    store[first.id] = first
    store[second.id] = second
    run(service.set_default_theme(session, second.id))
    assert second.is_default is True
    assert first.is_default is False


def test_to_out_compiles_styles(store, session):
    row = builtin_row()
    store[row.id] = row
    out = service.to_out(row)
    assert out.is_builtin is True and out.is_default is True
    assert out.styles["paragraph"]["font-size"]
    assert out.config.colors.primary


def test_resolve_theme_prefers_db_then_falls_back(store, session):
    row = builtin_row()
    store[row.id] = row
    resolved = run(service.resolve_theme(session, row.id))
    assert resolved.id == row.id
    assert resolved.styles["paragraph"]

    fallback = run(service.resolve_theme(session, "ghost"))
    assert fallback.id == DEFAULT_THEME_ID


def test_seed_builtin_themes_is_idempotent(store, session):
    run(service.seed_builtin_themes(session))
    assert len(store) == len(BUILTIN_THEMES)
    assert sum(1 for r in store.values() if r.is_default) == 1

    run(service.seed_builtin_themes(session))
    assert len(store) == len(BUILTIN_THEMES)
    assert sum(1 for r in store.values() if r.is_default) == 1


def test_seed_preserves_user_default(store, session):
    run(service.seed_builtin_themes(session))
    run(service.set_default_theme(session, "paperhub-warm"))
    run(service.seed_builtin_themes(session))
    assert store["paperhub-warm"].is_default is True


# ---------- REST API ----------


@pytest.fixture
def client(store, session, monkeypatch):
    from app.main import app

    monkeypatch.setattr(app_settings, "paperhub_api_key", "")
    app.dependency_overrides[get_session] = lambda: session
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(client, store, session):
    run(service.seed_builtin_themes(session))
    return store


def test_api_lists_builtin_themes(seeded, client):
    resp = client.get("/api/v1/wechat/themes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 5
    assert all(item["is_builtin"] for item in data)
    assert sum(1 for item in data if item["is_default"]) == 1
    assert data[0]["styles"]["paragraph"]
    assert data[0]["config"]["colors"]["primary"]


def test_api_create_custom_theme(seeded, client):
    resp = client.post(
        "/api/v1/wechat/themes",
        json={
            "name": "自定义蓝",
            "description": "测试",
            "config": {"colors": {"primary": "#0055FF"}},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_builtin"] is False
    assert body["config"]["colors"]["primary"] == "#0055FF"
    assert "#0055FF" in body["styles"]["h2"]["border-left"]


def test_api_create_rejects_invalid_config(seeded, client):
    resp = client.post(
        "/api/v1/wechat/themes",
        json={"name": "坏主题", "config": {"colors": {"primary": "red"}}},
    )
    assert resp.status_code == 422


def test_api_update_builtin_forbidden(seeded, client):
    resp = client.put(
        f"/api/v1/wechat/themes/{DEFAULT_THEME_ID}", json={"name": "hack"}
    )
    assert resp.status_code == 400


def test_api_delete_builtin_forbidden(seeded, client):
    resp = client.delete(f"/api/v1/wechat/themes/{DEFAULT_THEME_ID}")
    assert resp.status_code == 400


def test_api_full_custom_lifecycle(seeded, client):
    created = client.post(
        "/api/v1/wechat/themes",
        json={"name": "可编辑", "config": {"colors": {"primary": "#112233"}}},
    ).json()
    theme_id = created["id"]

    updated = client.put(
        f"/api/v1/wechat/themes/{theme_id}",
        json={"name": "已改名", "config": {"colors": {"primary": "#445566"}}},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "已改名"

    assert (
        client.delete(f"/api/v1/wechat/themes/{theme_id}").status_code == 204
    )
    assert client.get(f"/api/v1/wechat/themes/{theme_id}").status_code == 404


def test_api_duplicate_and_set_default(seeded, client):
    dup = client.post(f"/api/v1/wechat/themes/{DEFAULT_THEME_ID}/duplicate")
    assert dup.status_code == 201
    dup_body = dup.json()
    assert dup_body["is_builtin"] is False

    made_default = client.post(
        f"/api/v1/wechat/themes/{dup_body['id']}/set-default"
    )
    assert made_default.status_code == 200
    assert made_default.json()["is_default"] is True

    listing = client.get("/api/v1/wechat/themes").json()
    assert sum(1 for item in listing if item["is_default"]) == 1
