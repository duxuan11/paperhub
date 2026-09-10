"""微信发布链路测试（无需数据库 / Redis / 真实微信接口）。

覆盖三个曾经导致"点了没反应"的缺陷：
1. 微信 HTTP 200 + errcode!=0 被当成成功（draft/add 静默失败）
2. 草稿封面 thumb_media_id 为空（图文草稿必填，微信直接报 40007）
3. 正文 {{figure:N}} 占位符 / 本地图片地址没被替换成微信可访问的 URL
"""

import asyncio
import zlib

import pytest
from app.core.config import settings  # noqa: F401  —— 注册仓库根目录到 sys.path

from publishers.wechat.client import WeChatAPIError, WeChatClient, _check
from publishers.wechat.cover import default_cover_png
from publishers.wechat.formatter import markdown_to_wechat_html
from publishers.wechat.publisher import (
    MAX_CONTENT_LEN,
    MockWeChatPublisher,
    RealWeChatPublisher,
    build_article_payload,
)


def run(coro):
    return asyncio.run(coro)


# ---------- errcode 检查 ----------


def test_check_passes_on_ok():
    assert _check("api", {"errcode": 0, "errmsg": "ok", "media_id": "m1"})["media_id"] == "m1"
    assert _check("api", {"media_id": "m1"})["media_id"] == "m1"


def test_check_raises_with_actionable_hint_for_ip_whitelist():
    with pytest.raises(WeChatAPIError) as exc:
        _check("cgi-bin/token", {"errcode": 40164, "errmsg": "invalid ip 1.2.3.4, not in whitelist"})
    assert exc.value.errcode == 40164
    assert "IP白名单" in str(exc.value)


def test_check_raises_on_invalid_media_id():
    with pytest.raises(WeChatAPIError) as exc:
        _check("cgi-bin/draft/add", {"errcode": 40007, "errmsg": "invalid media_id"})
    assert exc.value.errcode == 40007
    assert "永久素材" in str(exc.value)


def test_check_rejects_non_dict():
    with pytest.raises(WeChatAPIError):
        _check("api", "<html>500</html>")


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """同一个 fake 客户端模拟"先取 token，再调业务接口"的两段请求。"""

    def __init__(self, payload, token_payload=None):
        self._payload = payload
        self._token_payload = token_payload or {
            "access_token": "FAKE_TOKEN",
            "expires_in": 7200,
        }
        self.calls: list[tuple[str, str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def _resp(self, url):
        if "cgi-bin/token" in url:
            return _FakeResponse(self._token_payload)
        return _FakeResponse(self._payload)

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._resp(url)

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._resp(url)


def _patch_httpx(monkeypatch, payload, token_payload=None):
    from publishers.wechat import client as client_mod

    fake = _FakeAsyncClient(payload, token_payload)
    monkeypatch.setattr(client_mod.httpx, "AsyncClient", lambda **kwargs: fake)
    return fake


def test_client_token_error_is_not_silent(monkeypatch):
    payload = {"errcode": 40164, "errmsg": "invalid ip 1.2.3.4, not in whitelist"}
    _patch_httpx(monkeypatch, payload, token_payload=payload)
    with pytest.raises(WeChatAPIError) as exc:
        run(WeChatClient("id", "secret").get_access_token())
    assert exc.value.errcode == 40164


def test_client_add_draft_raises_on_errcode(monkeypatch):
    _patch_httpx(monkeypatch, {"errcode": 40007, "errmsg": "invalid media_id"})
    with pytest.raises(WeChatAPIError):
        run(WeChatClient("id", "secret").add_draft([{"title": "t"}]))


def test_client_uploadimg_returns_url(monkeypatch):
    _patch_httpx(monkeypatch, {"errcode": 0, "url": "https://mmbiz.qpic.cn/x.png"})
    url = run(WeChatClient("id", "secret").upload_content_image(b"png", "a.png"))
    assert url == "https://mmbiz.qpic.cn/x.png"


def test_client_permanent_material_returns_media_id(monkeypatch):
    _patch_httpx(monkeypatch, {"errcode": 0, "media_id": "PERM123"})
    mid = run(WeChatClient("id", "secret").upload_permanent_image(b"png", "cover.png"))
    assert mid == "PERM123"


# ---------- 发布器 ----------


class _BoomClient:
    """所有接口都返回 40164，模拟未加白名单。"""

    async def get_access_token(self):
        raise WeChatAPIError("cgi-bin/token", 40164, "invalid ip 1.2.3.4, not in whitelist")

    async def add_draft(self, articles):
        await self.get_access_token()

    async def publish(self, media_id):
        await self.get_access_token()

    async def upload_content_image(self, data, filename):
        await self.get_access_token()

    async def upload_permanent_image(self, data, filename):
        await self.get_access_token()


def test_real_publisher_reports_error_instead_of_faking_success():
    pub = RealWeChatPublisher("id", "secret", client=_BoomClient())
    assert pub.is_mock() is False
    draft = run(pub.create_draft({"title": "t"}))
    assert draft.success is False
    assert "40164" in (draft.error or "")
    assert "IP白名单" in (draft.error or "")


class _DraftOnlyClient(_BoomClient):
    async def add_draft(self, articles):
        return {"media_id": "MEDIA1"}


def test_real_publisher_draft_without_media_id_is_failure():
    class _NoMediaClient(_DraftOnlyClient):
        async def add_draft(self, articles):
            return {"errcode": 0, "errmsg": "ok"}

    pub = RealWeChatPublisher("id", "secret", client=_NoMediaClient())
    draft = run(pub.create_draft({"title": "t"}))
    assert draft.success is False
    assert "media_id" in (draft.error or "")


def test_mock_publisher_helpers_return_placeholders():
    pub = MockWeChatPublisher()
    assert pub.is_mock() is True
    assert run(pub.upload_content_image(b"x", "a.png")).startswith("mock-image-")
    assert run(pub.upload_cover(b"x", "c.png")).startswith("mock-cover-")
    assert run(pub.create_draft({"title": "t"})).success is True


# ---------- 正文组装 ----------


def test_build_payload_sets_thumb_media_id_and_rewrites_images():
    md = "# 标题\n\n正文\n\n![Figure 1]({{figure:0}})\n\n还有散落的占位符 {{figure:1}}。"
    payload = build_article_payload(
        "标题",
        md,
        {"{{figure:0}}": "https://mmbiz.qpic.cn/0.png", "{{figure:1}}": "https://mmbiz.qpic.cn/1.png"},
        thumb_media_id="PERM_COVER",
        digest="D" * 200,
    )
    assert payload["thumb_media_id"] == "PERM_COVER"
    assert "<img src=\"https://mmbiz.qpic.cn/0.png\"" in payload["content"]
    assert "{{figure" not in payload["content"]
    assert "https://mmbiz.qpic.cn/1.png" in payload["content"]
    assert len(payload["digest"]) == 120
    assert payload["need_open_comment"] == 0
    assert payload["only_fans_can_comment"] == 0


def test_build_payload_rejects_overlong_content():
    with pytest.raises(ValueError) as exc:
        build_article_payload("标题", "x" * (MAX_CONTENT_LEN + 10))
    assert "微信限制" in str(exc.value)


def test_formatter_keeps_image_placeholders_replaced():
    html = markdown_to_wechat_html("![a]({{figure:0}})", {"{{figure:0}}": "http://img"})
    assert '<img src="http://img"' in html


# ---------- 默认封面 ----------


def test_default_cover_is_a_valid_gradient_png():
    data = default_cover_png(90, 38)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IHDR" in data and data.endswith(b"IEND\xaeB`\x82")
    # IHDR 紧跟签名：宽 90 高 38（大端 4 字节）
    assert data[16:20] == (90).to_bytes(4, "big")
    assert data[20:24] == (38).to_bytes(4, "big")
    assert len(zlib.decompress(data[41 : data.index(b"IEND") - 4])) > 0
