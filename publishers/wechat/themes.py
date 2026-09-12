"""微信公众号主题（Theme）注册表。

设计目标：**文章内容与视觉样式解耦**。

- 文章只保存 Markdown 正文；主题只描述「怎么显示」；
- 渲染器（``publishers.wechat.renderer``）负责把主题样式落到 inline style 的 HTML；
- 新增主题只需注册一个 :class:`WeChatTheme` 配置对象（或放一个 JSON 到
  ``publishers/wechat/themes/``），**不需要改渲染代码，也不需要动 React 组件**。

主题样式统一使用「CSS 属性 -> 值」的普通 dict，且全部是微信编辑器可接受的
inline style（不使用伪元素 / 外部 CSS / class），因此正文不依赖任何外部样式表。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# CSS 属性名 -> 值；值为纯字符串（如 "16px" / "#1f2328"）
Style = dict[str, str]
Styles = dict[str, Style]

DEFAULT_THEME_ID = "paperhub-science"


@dataclass
class WeChatTheme:
    id: str
    name: str
    description: str = ""
    styles: Styles = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    def css(self, key: str) -> Style:
        """取某个元素的样式；未定义时返回空 dict（渲染器会退化为无 style）。"""
        return self.styles.get(key, {}) or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "styles": self.styles,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeChatTheme":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            description=str(data.get("description") or ""),
            styles={k: dict(v) for k, v in (data.get("styles") or {}).items()},
            options=dict(data.get("options") or {}),
        )


# --------------------------------------------------------------------------
# 注册表
# --------------------------------------------------------------------------

_REGISTRY: dict[str, WeChatTheme] = {}


def register_theme(theme: WeChatTheme) -> WeChatTheme:
    """注册（或覆盖）一个主题，返回该主题。供内置主题与第三方扩展使用。"""
    _REGISTRY[theme.id] = theme
    return theme


def get_theme(theme_id: str | None = None) -> WeChatTheme:
    """按 id 取主题；未知 / 缺省时回退到默认主题，永不抛错。"""
    theme = _REGISTRY.get(theme_id or "")
    if theme is None:
        theme = _REGISTRY[DEFAULT_THEME_ID]
    return theme


def list_themes() -> list[WeChatTheme]:
    """按注册顺序返回全部主题。"""
    return list(_REGISTRY.values())


def load_theme_dir(directory: Path) -> list[str]:
    """从目录加载 ``*.json`` 主题文件（可选扩展点），返回加载到的主题 id。"""
    loaded: list[str] = []
    if not directory.is_dir():
        return loaded
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    loaded.append(register_theme(WeChatTheme.from_dict(item)).id)
            else:
                loaded.append(register_theme(WeChatTheme.from_dict(data)).id)
        except (OSError, ValueError, KeyError):
            # 单个主题文件损坏不应影响整个发布链路
            continue
    return loaded


# --------------------------------------------------------------------------
# 内置主题：PaperHub Science（默认）+ PaperHub Minimal（第二套示例）
# --------------------------------------------------------------------------

PAPERHUB_SCIENCE = WeChatTheme(
    id=DEFAULT_THEME_ID,
    name="PaperHub Science",
    description="简洁、专业、现代的科研解读主题，适合 AI / 生物医学 / 论文解读。",
    styles={
        "article": {
            "font-family": "-apple-system,BlinkMacSystemFont,'PingFang SC',"
            "'Hiragino Sans GB','Microsoft YaHei',sans-serif",
            "font-size": "16px",
            "line-height": "1.8",
            "color": "#1f2328",
            "background-color": "#ffffff",
            "letter-spacing": "0.2px",
            "word-break": "break-word",
        },
        "h1": {
            "font-size": "22px",
            "font-weight": "700",
            "color": "#0f172a",
            "line-height": "1.4",
            "margin": "28px 0 14px",
        },
        "h2": {
            "font-size": "19px",
            "font-weight": "700",
            "color": "#0f172a",
            "line-height": "1.5",
            "margin": "26px 0 12px",
            "padding-left": "10px",
            "border-left": "4px solid #2563eb",
        },
        "h3": {
            "font-size": "17px",
            "font-weight": "600",
            "color": "#1e293b",
            "line-height": "1.5",
            "margin": "20px 0 8px",
        },
        "paragraph": {
            "font-size": "16px",
            "line-height": "1.8",
            "color": "#334155",
            "margin": "0 0 16px",
        },
        "blockquote": {
            "margin": "0 0 16px",
            "padding": "12px 16px",
            "background-color": "#f8fafc",
            "border-left": "3px solid #93c5fd",
            "color": "#475569",
            "font-size": "15px",
            "line-height": "1.7",
            "border-radius": "0 6px 6px 0",
        },
        "image": {
            "display": "block",
            "width": "100%",
            "max-width": "100%",
            "height": "auto",
            "margin": "18px auto 6px",
            "border-radius": "8px",
        },
        "caption": {
            "font-size": "13px",
            "color": "#94a3b8",
            "text-align": "center",
            "line-height": "1.6",
            "margin": "0 0 18px",
        },
        "ul": {"margin": "0 0 16px", "padding-left": "22px"},
        "ol": {"margin": "0 0 16px", "padding-left": "22px"},
        "li": {
            "font-size": "16px",
            "line-height": "1.8",
            "color": "#334155",
            "margin": "0 0 6px",
        },
        "hr": {
            "border": "none",
            "border-top": "1px solid #e2e8f0",
            "margin": "24px 0",
        },
        "link": {
            "color": "#2563eb",
            "text-decoration": "none",
            "border-bottom": "1px solid #bfdbfe",
        },
        "strong": {"font-weight": "600", "color": "#0f172a"},
        "em": {"font-style": "italic", "color": "#475569"},
        "code": {
            "background-color": "#f1f5f9",
            "color": "#be123c",
            "padding": "2px 5px",
            "border-radius": "4px",
            "font-size": "14px",
            "font-family": "Menlo,Consolas,monospace",
        },
        "pre": {
            "background-color": "#0f172a",
            "color": "#e2e8f0",
            "padding": "14px 16px",
            "border-radius": "8px",
            "font-size": "13px",
            "line-height": "1.6",
            "overflow-x": "auto",
            "margin": "0 0 16px",
        },
        "table": {
            "width": "100%",
            "border-collapse": "collapse",
            "margin": "0 0 16px",
            "font-size": "14px",
        },
        "th": {
            "border": "1px solid #e2e8f0",
            "background-color": "#f8fafc",
            "padding": "8px 10px",
            "text-align": "left",
            "font-weight": "600",
            "color": "#0f172a",
        },
        "td": {
            "border": "1px solid #e2e8f0",
            "padding": "8px 10px",
            "text-align": "left",
            "color": "#334155",
        },
    },
)

PAPERHUB_MINIMAL = WeChatTheme(
    id="paperhub-minimal",
    name="PaperHub Minimal",
    description="极简黑白主题，去掉强调色，适合以文字为主的快讯 / 摘要。",
    styles={
        "article": {
            "font-family": "-apple-system,BlinkMacSystemFont,'PingFang SC',"
            "'Microsoft YaHei',sans-serif",
            "font-size": "16px",
            "line-height": "1.75",
            "color": "#262626",
            "background-color": "#ffffff",
        },
        "h1": {
            "font-size": "21px",
            "font-weight": "700",
            "color": "#111111",
            "margin": "24px 0 12px",
            "line-height": "1.4",
        },
        "h2": {
            "font-size": "18px",
            "font-weight": "700",
            "color": "#111111",
            "margin": "22px 0 10px",
            "line-height": "1.5",
        },
        "h3": {
            "font-size": "16px",
            "font-weight": "600",
            "color": "#333333",
            "margin": "18px 0 8px",
            "line-height": "1.5",
        },
        "paragraph": {
            "font-size": "16px",
            "line-height": "1.75",
            "color": "#404040",
            "margin": "0 0 14px",
        },
        "blockquote": {
            "margin": "0 0 14px",
            "padding": "10px 14px",
            "background-color": "#f5f5f5",
            "color": "#595959",
            "font-size": "15px",
            "line-height": "1.7",
        },
        "image": {
            "display": "block",
            "width": "100%",
            "max-width": "100%",
            "height": "auto",
            "margin": "16px auto 6px",
        },
        "caption": {
            "font-size": "13px",
            "color": "#8c8c8c",
            "text-align": "center",
            "line-height": "1.6",
            "margin": "0 0 16px",
        },
        "ul": {"margin": "0 0 14px", "padding-left": "20px"},
        "ol": {"margin": "0 0 14px", "padding-left": "20px"},
        "li": {
            "font-size": "16px",
            "line-height": "1.75",
            "color": "#404040",
            "margin": "0 0 5px",
        },
        "hr": {
            "border": "none",
            "border-top": "1px solid #e5e5e5",
            "margin": "22px 0",
        },
        "link": {"color": "#1a1a1a", "text-decoration": "underline"},
        "strong": {"font-weight": "600", "color": "#111111"},
        "em": {"font-style": "italic", "color": "#595959"},
        "code": {
            "background-color": "#f5f5f5",
            "color": "#262626",
            "padding": "2px 5px",
            "border-radius": "3px",
            "font-size": "14px",
            "font-family": "Menlo,Consolas,monospace",
        },
        "pre": {
            "background-color": "#f5f5f5",
            "color": "#262626",
            "padding": "14px 16px",
            "border-radius": "6px",
            "font-size": "13px",
            "line-height": "1.6",
            "overflow-x": "auto",
            "margin": "0 0 14px",
        },
        "table": {
            "width": "100%",
            "border-collapse": "collapse",
            "margin": "0 0 14px",
            "font-size": "14px",
        },
        "th": {
            "border": "1px solid #e5e5e5",
            "background-color": "#fafafa",
            "padding": "8px 10px",
            "text-align": "left",
            "font-weight": "600",
        },
        "td": {
            "border": "1px solid #e5e5e5",
            "padding": "8px 10px",
            "text-align": "left",
            "color": "#404040",
        },
    },
)

register_theme(PAPERHUB_SCIENCE)
register_theme(PAPERHUB_MINIMAL)

# 可选：从 publishers/wechat/themes/*.json 加载第三方主题
load_theme_dir(Path(__file__).resolve().parent / "themes")
