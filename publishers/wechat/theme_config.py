"""微信公众号 Theme 的「设计变量 -> 组件样式」编译器。

设计原则（见需求「不要把模板设计成一段 HTML 字符串」）：

- 用户编辑的是**设计变量**：配色（colors）、字体排版（typography）与少量组件
  覆盖（components），而不是一大段 CSS；
- :func:`compile_styles` 把它们编译成渲染器直接消费的「元素 -> CSS 属性」表
  （``Styles``）。渲染器 ``publishers/wechat/renderer.py`` 与本模块解耦；
- 编译结果**永远是微信可内联的普通 CSS 属性**，不含变量 / 伪元素 / 外部样式表。

前端 `frontend/lib/themeConfig.ts` 镜像了同一套编译规则，用于模板编辑器的实时
预览；发布链路始终使用本模块（后端）的编译结果，保证「所见即所得」。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# CSS 属性名 -> 值
Style = dict[str, str]
Styles = dict[str, Style]

FONT_STACK = (
    "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB',"
    "'Microsoft YaHei',sans-serif"
)
MONO_STACK = "Menlo,Consolas,'Courier New',monospace"

# 默认设计变量：任何缺失字段都会回退到这里，保证编译结果始终完整
DEFAULT_CONFIG: dict[str, Any] = {
    "colors": {
        "primary": "#2563EB",
        "secondary": "#64748B",
        "text": "#1E293B",
        "muted": "#64748B",
        "background": "#FFFFFF",
        "border": "#E2E8F0",
    },
    "typography": {
        "fontFamily": FONT_STACK,
        "bodySize": "15px",
        "bodyLineHeight": "1.8",
        "heading1Size": "24px",
        "heading2Size": "19px",
        "heading3Size": "17px",
        "captionSize": "13px",
    },
    # 组件级覆盖：{元素 key: {css 属性: 值}}，叠加在 colors/typography 编译结果之上
    "components": {},
}

# 组件编辑器暴露的元素 key（与渲染器使用的 style key 一致）
COMPONENT_KEYS = (
    "paragraph",
    "h1",
    "h2",
    "h3",
    "blockquote",
    "callout",
    "calloutTitle",
    "image",
    "caption",
    "code",
    "pre",
    "table",
    "th",
    "td",
    "hr",
    "link",
)


def merge_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """把用户 config 深合并到 :data:`DEFAULT_CONFIG`，返回完整配置（新对象）。"""
    cfg = deepcopy(DEFAULT_CONFIG)
    if not config:
        return cfg
    for section in ("colors", "typography"):
        for key, value in (config.get(section) or {}).items():
            if value is not None and value != "":
                cfg[section][key] = value
    components = config.get("components") or {}
    cfg["components"] = {
        str(key): dict(value)
        for key, value in components.items()
        if isinstance(value, dict)
    }
    return cfg


def _parse_hex(color: str) -> tuple[int, int, int] | None:
    """解析 #RGB / #RRGGBB；失败返回 None（编译阶段不抛错，保持发布链路健壮）。"""
    if not isinstance(color, str):
        return None
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        return None
    try:
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
    except ValueError:
        return None


def tint(color: str, ratio: float) -> str:
    """把颜色按 ``ratio`` 混向白色（0=原色，1=纯白），用于生成浅色底。"""
    rgb = _parse_hex(color)
    if rgb is None:
        return color
    r, g, b = rgb
    ratio = max(0.0, min(1.0, ratio))
    mix = lambda ch: round(ch + (255 - ch) * ratio)  # noqa: E731
    return "#%02x%02x%02x" % (mix(r), mix(g), mix(b))


def compile_styles(config: dict[str, Any] | None = None) -> Styles:
    """把设计变量编译为渲染器使用的元素样式表（全部为合法 inline CSS）。"""
    cfg = merge_config(config)
    c = cfg["colors"]
    t = cfg["typography"]
    primary = c["primary"]
    text = c["text"]
    body_size = t["bodySize"]
    line_height = t["bodyLineHeight"]

    styles: Styles = {
        "article": {
            "font-family": t["fontFamily"],
            "font-size": body_size,
            "line-height": line_height,
            "color": text,
            "background-color": c["background"],
            "letter-spacing": "0.2px",
            "word-break": "break-word",
        },
        "h1": {
            "font-size": t["heading1Size"],
            "font-weight": "700",
            "color": text,
            "line-height": "1.4",
            "margin": "28px 0 14px",
        },
        "h2": {
            "font-size": t["heading2Size"],
            "font-weight": "700",
            "color": text,
            "line-height": "1.5",
            "margin": "26px 0 12px",
            "padding-left": "10px",
            "border-left": f"4px solid {primary}",
        },
        "h3": {
            "font-size": t["heading3Size"],
            "font-weight": "600",
            "color": text,
            "line-height": "1.5",
            "margin": "20px 0 8px",
        },
        "h4": {
            "font-size": body_size,
            "font-weight": "600",
            "color": text,
            "line-height": "1.5",
            "margin": "18px 0 8px",
        },
        "h5": {
            "font-size": "14px",
            "font-weight": "600",
            "color": text,
            "margin": "16px 0 6px",
        },
        "h6": {
            "font-size": "13px",
            "font-weight": "600",
            "color": c["muted"],
            "margin": "14px 0 6px",
        },
        "paragraph": {
            "font-size": body_size,
            "line-height": line_height,
            "color": text,
            "margin": "0 0 16px",
        },
        "blockquote": {
            "margin": "0 0 16px",
            "padding": "12px 16px",
            "background-color": tint(primary, 0.94),
            "border-left": f"3px solid {tint(primary, 0.55)}",
            "color": c["secondary"],
            "font-size": body_size,
            "line-height": "1.7",
            "border-radius": "0 6px 6px 0",
        },
        "callout": {
            "margin": "0 0 16px",
            "padding": "12px 16px",
            "background-color": tint(primary, 0.92),
            "border-left": f"3px solid {primary}",
            "border-radius": "0 6px 6px 0",
        },
        "calloutTitle": {
            "font-size": body_size,
            "font-weight": "600",
            "color": primary,
            "margin": "0 0 6px",
        },
        "calloutText": {
            "font-size": body_size,
            "line-height": line_height,
            "color": text,
            "margin": "0",
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
            "font-size": t["captionSize"],
            "color": c["muted"],
            "text-align": "center",
            "line-height": "1.6",
            "margin": "0 0 18px",
        },
        "ul": {"margin": "0 0 16px", "padding-left": "22px"},
        "ol": {"margin": "0 0 16px", "padding-left": "22px"},
        "li": {
            "font-size": body_size,
            "line-height": line_height,
            "color": text,
            "margin": "0 0 6px",
        },
        "hr": {
            "border": "none",
            "border-top": f"1px solid {c['border']}",
            "margin": "24px 0",
        },
        "link": {
            "color": primary,
            "text-decoration": "none",
            "border-bottom": f"1px solid {tint(primary, 0.7)}",
        },
        "strong": {"font-weight": "600", "color": text},
        "em": {"font-style": "italic", "color": c["secondary"]},
        "code": {
            "background-color": tint(primary, 0.92),
            "color": primary,
            "padding": "2px 5px",
            "border-radius": "4px",
            "font-size": "14px",
            "font-family": MONO_STACK,
        },
        "pre": {
            "background-color": text,
            "color": "#F8FAFC",
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
            "border": f"1px solid {c['border']}",
            "background-color": tint(primary, 0.94),
            "padding": "8px 10px",
            "text-align": "left",
            "font-weight": "600",
            "color": text,
        },
        "td": {
            "border": f"1px solid {c['border']}",
            "padding": "8px 10px",
            "text-align": "left",
            "color": text,
        },
    }

    for key, overrides in cfg["components"].items():
        if key in styles:
            styles[key] = {
                **styles[key],
                **{k: str(v) for k, v in overrides.items() if v},
            }
    return styles
