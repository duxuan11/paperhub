"""Markdown -> 微信公众号 HTML 格式化（向后兼容入口）。

历史上本模块自带一套简易转换逻辑；现在样式统一由 Theme 驱动，真正的渲染在
:mod:`publishers.wechat.renderer`。这里保留 ``markdown_to_wechat_html`` 以便旧
调用方（以及测试）继续工作，默认使用 PaperHub Science 主题。
"""

from __future__ import annotations

from publishers.wechat.renderer import escape, render_markdown_html, style_attr
from publishers.wechat.themes import DEFAULT_THEME_ID, WeChatTheme, get_theme

__all__ = ["escape", "style_attr", "markdown_to_wechat_html"]


def markdown_to_wechat_html(
    md: str,
    image_map: dict[str, str] | None = None,
    theme: WeChatTheme | str | None = None,
) -> str:
    """兼容旧签名：``(md, image_map)``；新增可选 ``theme``（对象或 id）。"""
    if isinstance(theme, str):
        theme = get_theme(theme)
    return render_markdown_html(md, theme or get_theme(DEFAULT_THEME_ID), image_map)
