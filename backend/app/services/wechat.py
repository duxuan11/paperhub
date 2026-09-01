"""微信公众号发布服务门面：选择真实或 Mock 发布器。"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保仓库根目录在 sys.path，使 publishers 包可被导入（原生与 Docker 通用）
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.config import settings  # noqa: E402
from publishers.wechat.publisher import (  # noqa: E402
    DraftResult,
    PublishResult,
    WeChatPublisher,
    RealWeChatPublisher,
    MockWeChatPublisher,
    build_article_payload,
)

__all__ = [
    "DraftResult",
    "PublishResult",
    "WeChatPublisher",
    "RealWeChatPublisher",
    "MockWeChatPublisher",
    "build_article_payload",
    "get_publisher",
]


def get_publisher() -> WeChatPublisher:
    if settings.wechat_app_id and settings.wechat_app_secret:
        return RealWeChatPublisher(settings.wechat_app_id, settings.wechat_app_secret)
    return MockWeChatPublisher()
