"""微信公众号发布器：接口 + 真实实现 + Mock 实现。

安全设计：默认只创建草稿（draft），不直接发布。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from publishers.wechat.client import WeChatClient
from publishers.wechat.renderer import render_markdown_html
from publishers.wechat.themes import DEFAULT_THEME_ID, get_theme

# 微信正文长度上限（字符）
MAX_CONTENT_LEN = 20000
# 微信摘要长度上限（字符）
MAX_DIGEST_LEN = 120


@dataclass
class DraftResult:
    success: bool
    external_id: str | None = None
    error: str | None = None
    mock: bool = False


@dataclass
class PublishResult:
    success: bool
    external_id: str | None = None
    error: str | None = None
    mock: bool = False


def _err(e: Exception) -> str:
    return str(e) or e.__class__.__name__


class WeChatPublisher:
    def is_mock(self) -> bool:
        raise NotImplementedError

    async def create_draft(self, article: dict) -> DraftResult:
        """article: {title, content(html), thumb_media_id, ...}"""
        raise NotImplementedError

    async def publish(self, external_id: str) -> PublishResult:
        raise NotImplementedError

    async def upload_content_image(self, data: bytes, filename: str) -> str:
        """上传正文图片，返回微信侧可访问的 URL。"""
        raise NotImplementedError

    async def upload_cover(self, data: bytes, filename: str) -> str:
        """上传封面素材，返回可作 thumb_media_id 的永久 media_id。"""
        raise NotImplementedError


class RealWeChatPublisher(WeChatPublisher):
    def __init__(self, app_id: str, app_secret: str, client: WeChatClient | None = None) -> None:
        self.client = client or WeChatClient(app_id, app_secret)

    def is_mock(self) -> bool:
        return False

    async def create_draft(self, article: dict) -> DraftResult:
        try:
            data = await self.client.add_draft([article])
        except Exception as e:  # noqa: BLE001
            return DraftResult(success=False, error=_err(e), mock=False)
        media_id = data.get("media_id")
        if not media_id:
            return DraftResult(
                success=False, error=f"微信未返回 media_id: {data}", mock=False
            )
        return DraftResult(success=True, external_id=str(media_id), mock=False)

    async def publish(self, external_id: str) -> PublishResult:
        try:
            data = await self.client.publish(external_id)
        except Exception as e:  # noqa: BLE001
            return PublishResult(success=False, error=_err(e), mock=False)
        return PublishResult(
            success=True, external_id=str(data.get("publish_id") or ""), mock=False
        )

    async def upload_content_image(self, data: bytes, filename: str) -> str:
        return await self.client.upload_content_image(data, filename)

    async def upload_cover(self, data: bytes, filename: str) -> str:
        return await self.client.upload_permanent_image(data, filename)


class MockWeChatPublisher(WeChatPublisher):
    """未配置 WECHAT_APP_ID / SECRET 时使用：只落到本地记录，不调用微信。"""

    def is_mock(self) -> bool:
        return True

    async def create_draft(self, article: dict) -> DraftResult:
        return DraftResult(
            success=True, external_id=f"mock-draft-{uuid.uuid4().hex[:12]}", mock=True
        )

    async def publish(self, external_id: str) -> PublishResult:
        return PublishResult(
            success=True, external_id=f"mock-publish-{uuid.uuid4().hex[:12]}", mock=True
        )

    async def upload_content_image(self, data: bytes, filename: str) -> str:
        return f"mock-image-{uuid.uuid4().hex[:12]}"

    async def upload_cover(self, data: bytes, filename: str) -> str:
        return f"mock-cover-{uuid.uuid4().hex[:12]}"


def build_article_payload(
    title: str,
    content_md: str,
    image_map: dict[str, str] | None = None,
    *,
    thumb_media_id: str = "",
    author: str = "PaperHub",
    digest: str = "",
    content_source_url: str = "",
    theme: str | None = None,
) -> dict:
    """把 markdown 文章组装成 draft/add 的 articles[] 元素。

    content: HTML（图片已替换为微信可访问的 mmbiz URL，且全部为 inline style）
    thumb_media_id: 封面永久素材 media_id —— 图文消息（news）必填
    theme: 主题 id；未知 / 缺省时回退到默认主题（PaperHub Science）
    """
    html = render_markdown_html(content_md, get_theme(theme or DEFAULT_THEME_ID), image_map)
    if len(html) > MAX_CONTENT_LEN:
        raise ValueError(
            f"正文长度 {len(html)} 超过微信限制 {MAX_CONTENT_LEN} 字符，"
            "请先在编辑器里用「AI 缩短」精简后再推送"
        )
    return {
        "title": title or "未命名",
        "author": author,
        "content": html,
        "digest": (digest or "").strip()[:MAX_DIGEST_LEN],
        "content_source_url": content_source_url,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
