"""微信公众号发布器：接口 + 真实实现 + Mock 实现。

安全设计：默认只创建草稿（draft），不直接发布。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from publishers.wechat.client import WeChatClient
from publishers.wechat.formatter import markdown_to_wechat_html


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


class WeChatPublisher:
    def is_mock(self) -> bool:
        raise NotImplementedError

    async def create_draft(self, article: dict) -> DraftResult:
        """article: {title, content(html), thumb_media_id, ...}"""
        raise NotImplementedError

    async def publish(self, external_id: str) -> PublishResult:
        raise NotImplementedError


class RealWeChatPublisher(WeChatPublisher):
    def __init__(self, app_id: str, app_secret: str) -> None:
        self.client = WeChatClient(app_id, app_secret)

    def is_mock(self) -> bool:
        return False

    async def create_draft(self, article: dict) -> DraftResult:
        try:
            data = await self.client.add_draft([article])
            return DraftResult(
                success=True, external_id=data.get("media_id"), mock=False
            )
        except Exception as e:  # noqa: BLE001
            return DraftResult(success=False, error=str(e), mock=False)

    async def publish(self, external_id: str) -> PublishResult:
        try:
            data = await self.client.publish(external_id)
            return PublishResult(
                success=True, external_id=data.get("publish_id"), mock=False
            )
        except Exception as e:  # noqa: BLE001
            return PublishResult(success=False, error=str(e), mock=False)


class MockWeChatPublisher(WeChatPublisher):
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


def build_article_payload(
    title: str, content_md: str, image_map: dict[str, str] | None = None
) -> dict:
    html = markdown_to_wechat_html(content_md, image_map)
    return {
        "title": title,
        "author": "PaperHub",
        "content": html,
        "digest": "",
        "content_source_url": "",
        "thumb_media_id": "",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
