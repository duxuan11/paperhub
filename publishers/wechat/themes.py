"""微信公众号主题（Theme）注册表。

设计目标：**文章内容与视觉样式解耦**。

- 文章只保存 Markdown 正文；主题只描述「怎么显示」；
- 主题由**设计变量**定义（配色 colors / 字体排版 typography / 组件覆盖
  components），由 :mod:`publishers.wechat.theme_config` 编译成
  「元素 -> CSS 属性」表；
- 渲染器（``publishers.wechat.renderer``）负责把编译后的样式落到 inline style
  的 HTML，**不需要改渲染代码，也不需要动 React 组件**。

主题样式统一使用「CSS 属性 -> 值」的普通 dict，且全部是微信编辑器可接受的
inline style（不使用伪元素 / 外部 CSS / class / CSS 变量），因此正文不依赖任何
外部样式表。

内置主题定义在 :data:`BUILTIN_THEMES`；用户自定义主题持久化在数据库
``wechat_article_themes``，由 ``app.services.wechat_theme`` 加载后编译为同样的
``styles`` 结构，发布链路使用同一套渲染器。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from publishers.wechat.theme_config import (
    Style,
    Styles,
    compile_styles,
    merge_config,
)

__all__ = [
    "DEFAULT_THEME_ID",
    "Style",
    "Styles",
    "WeChatTheme",
    "BUILTIN_THEMES",
    "register_theme",
    "get_theme",
    "list_themes",
    "load_theme_dir",
]

DEFAULT_THEME_ID = "paperhub-science"

# 衬线字体栈：杂志 / 国风主题的标题使用，提升人文质感
SERIF_STACK = (
    "'Songti SC','Noto Serif SC','Source Han Serif SC',Georgia,"
    "'Times New Roman',serif"
)


@dataclass
class WeChatTheme:
    id: str
    name: str
    description: str = ""
    styles: Styles = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] | None = None
    is_builtin: bool = False

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
            "config": self.config,
            "is_builtin": self.is_builtin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeChatTheme":
        config = data.get("config")
        styles = {k: dict(v) for k, v in (data.get("styles") or {}).items()}
        # 只给了设计变量时，即时编译成渲染器可用的样式
        if config and not styles:
            styles = compile_styles(config)
        elif config:
            config = merge_config(config)
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or data["id"]),
            description=str(data.get("description") or ""),
            styles=styles,
            options=dict(data.get("options") or {}),
            config=config,
            is_builtin=bool(data.get("is_builtin", False)),
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
    """按注册顺序返回全部内置 / 静态主题。"""
    return list(_REGISTRY.values())


def load_theme_dir(directory: Path) -> list[str]:
    """从目录加载 ``*.json`` 主题文件（可选扩展点），返回加载到的主题 id。

    JSON 可以只给 ``config``（设计变量），也可以给完整的 ``styles``。
    """
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
# 内置主题（is_builtin = True，只读，不可删除）
# --------------------------------------------------------------------------

def _builtin(
    theme_id: str,
    name: str,
    description: str,
    config: dict[str, Any],
) -> WeChatTheme:
    merged = merge_config(config)
    return WeChatTheme(
        id=theme_id,
        name=name,
        description=description,
        styles=compile_styles(merged),
        options={},
        config=merged,
        is_builtin=True,
    )


BUILTIN_THEMES: list[WeChatTheme] = [
    _builtin(
        DEFAULT_THEME_ID,
        "PaperHub Science",
        "简洁、专业、现代的科研解读主题，适合 AI / 生物医学 / 论文解读。",
        {
            "colors": {
                "primary": "#2563EB",
                "secondary": "#475569",
                "text": "#1E293B",
                "muted": "#94A3B8",
                "background": "#FFFFFF",
                "border": "#E2E8F0",
            },
            "typography": {
                "bodySize": "16px",
                "bodyLineHeight": "1.8",
                "heading1Size": "22px",
                "heading2Size": "19px",
                "heading3Size": "17px",
                "captionSize": "13px",
            },
        },
    ),
    _builtin(
        "paperhub-minimal",
        "PaperHub Minimal",
        "极简黑白主题，去掉强调色，适合以文字为主的快讯 / 摘要。",
        {
            "colors": {
                "primary": "#1A1A1A",
                "secondary": "#595959",
                "text": "#262626",
                "muted": "#8C8C8C",
                "background": "#FFFFFF",
                "border": "#E5E5E5",
            },
            "typography": {
                "bodySize": "16px",
                "bodyLineHeight": "1.75",
                "heading1Size": "21px",
                "heading2Size": "18px",
                "heading3Size": "16px",
                "captionSize": "13px",
            },
        },
    ),
    _builtin(
        "paperhub-academic-blue",
        "Academic Blue",
        "经典学术蓝，适合科研论文、AI、生物医学等严肃主题。",
        {
            "colors": {
                "primary": "#1D4ED8",
                "secondary": "#475569",
                "text": "#0F172A",
                "muted": "#64748B",
                "background": "#FFFFFF",
                "border": "#DBEAFE",
            },
            "typography": {
                "bodySize": "15px",
                "bodyLineHeight": "1.8",
                "heading1Size": "24px",
                "heading2Size": "19px",
                "heading3Size": "17px",
                "captionSize": "13px",
            },
        },
    ),
    _builtin(
        "paperhub-nature",
        "Nature Green",
        "自然青绿配色，适合生命科学、生态、医学方向的解读。",
        {
            "colors": {
                "primary": "#15803D",
                "secondary": "#4B6355",
                "text": "#1C2B21",
                "muted": "#6B7F72",
                "background": "#FFFFFF",
                "border": "#DCFCE7",
            },
            "typography": {
                "bodySize": "15px",
                "bodyLineHeight": "1.8",
                "heading1Size": "23px",
                "heading2Size": "19px",
                "heading3Size": "17px",
                "captionSize": "13px",
            },
        },
    ),
    _builtin(
        "paperhub-warm",
        "Warm Reading",
        "暖色阅读主题，米色背景 + 琥珀强调，适合长文精读。",
        {
            "colors": {
                "primary": "#B45309",
                "secondary": "#7C5C3E",
                "text": "#3F2D20",
                "muted": "#9A7B5F",
                "background": "#FFFBF5",
                "border": "#FDE68A",
            },
            "typography": {
                "bodySize": "15px",
                "bodyLineHeight": "1.85",
                "heading1Size": "23px",
                "heading2Size": "19px",
                "heading3Size": "17px",
                "captionSize": "13px",
            },
        },
    ),
    _builtin(
        "paperhub-tech",
        "Tech Indigo",
        "科技镜蓝：色块章节标题 + 高对比表头，适合 AI / 工程 / 计算类论文。",
        {
            "colors": {
                "primary": "#4F46E5",
                "secondary": "#475569",
                "text": "#0F172A",
                "muted": "#64748B",
                "background": "#FFFFFF",
                "border": "#E0E7FF",
            },
            "typography": {
                "bodySize": "15px",
                "bodyLineHeight": "1.8",
                "heading1Size": "24px",
                "heading2Size": "19px",
                "heading3Size": "17px",
                "captionSize": "12px",
            },
            "components": {
                "h2": {
                    "background-color": "#EEF2FF",
                    "border-left": "4px solid #4F46E5",
                },
                "h3": {
                    "color": "#4F46E5",
                    "border-bottom": "1px dashed #C7D2FE",
                },
                "code": {"background-color": "#EEF2FF", "color": "#4338CA"},
            },
        },
    ),
    _builtin(
        "paperhub-editorial",
        "Editorial Serif",
        "杂志米白：衬线标题 + 大留白，适合综述 / 长文精读。",
        {
            "colors": {
                "primary": "#9A3412",
                "secondary": "#57534E",
                "text": "#1C1917",
                "muted": "#A8A29E",
                "background": "#FDFCFA",
                "border": "#E7E0D8",
            },
            "typography": {
                "fontFamily": SERIF_STACK,
                "bodySize": "16px",
                "bodyLineHeight": "1.9",
                "heading1Size": "26px",
                "heading2Size": "20px",
                "heading3Size": "17px",
                "captionSize": "12px",
            },
            "components": {
                "h1": {
                    "font-family": SERIF_STACK,
                    "letter-spacing": "1px",
                    "border-bottom": "1px solid #E7E0D8",
                },
                "h2": {
                    "background-color": "transparent",
                    "border-left": "none",
                    "border-bottom": "2px solid #9A3412",
                    "border-radius": "0",
                    "padding": "0 0 8px",
                },
                "h3": {"color": "#9A3412", "border-bottom": "none"},
                "blockquote": {
                    "background-color": "transparent",
                    "border": "none",
                    "border-left": "3px solid #9A3412",
                    "border-radius": "0",
                    "font-style": "italic",
                },
                "image": {"border-radius": "0", "box-shadow": "none"},
            },
        },
    ),
    _builtin(
        "paperhub-ink",
        "Ink Classic",
        "国风墨色：米纸底 + 朱砂红强调，适合人文 / 医学 / 交叉学科。",
        {
            "colors": {
                "primary": "#8C1D18",
                "secondary": "#57534E",
                "text": "#1F1B16",
                "muted": "#8A8175",
                "background": "#FAF8F2",
                "border": "#E5DED0",
            },
            "typography": {
                "fontFamily": SERIF_STACK,
                "bodySize": "16px",
                "bodyLineHeight": "1.9",
                "heading1Size": "25px",
                "heading2Size": "20px",
                "heading3Size": "17px",
                "captionSize": "12px",
            },
            "components": {
                "h1": {"font-family": SERIF_STACK, "letter-spacing": "2px"},
                "h2": {
                    "background-color": "#F3EDE1",
                    "border-left": "4px solid #8C1D18",
                    "border-radius": "0",
                },
                "h3": {
                    "color": "#8C1D18",
                    "border-bottom": "1px solid #E5DED0",
                },
                "hr": {"border-top": "2px solid #8C1D18", "width": "60px"},
            },
        },
    ),
]

for _theme in BUILTIN_THEMES:
    register_theme(_theme)

# 可选：从 publishers/wechat/themes/*.json 加载第三方主题
load_theme_dir(Path(__file__).resolve().parent / "themes")
