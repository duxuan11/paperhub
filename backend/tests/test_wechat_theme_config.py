"""主题设计变量编译器 + 内置主题 + 微信 Renderer 组件测试（无需数据库）。

覆盖：
1. ``compile_styles``：colors / typography 会落到各组件；components 覆盖生效；
2. 5 个内置主题定义完整且不可为空白；
3. Pydantic 校验：非法颜色 / 字号被拒绝；
4. Renderer：标题 / 正文 / 引用 / Callout / 图片 / 图注 / 表格 / 代码块都输出
   inline style，且不含 ``<script>`` / ``<link>`` / ``<style>`` / ``class``。
"""

import pytest
from app.core.config import settings  # noqa: F401  —— 注册仓库根目录到 sys.path
from pydantic import ValidationError

from app.schemas import WeChatThemeConfig
from publishers.wechat.renderer import render_markdown_html
from publishers.wechat.theme_config import (
    DEFAULT_CONFIG,
    compile_styles,
    merge_config,
    tint,
)
from publishers.wechat.themes import BUILTIN_THEMES, DEFAULT_THEME_ID, get_theme

REQUIRED_STYLE_KEYS = (
    "article",
    "h1",
    "h2",
    "h3",
    "paragraph",
    "blockquote",
    "callout",
    "calloutTitle",
    "image",
    "caption",
    "ul",
    "ol",
    "li",
    "hr",
    "link",
    "strong",
    "em",
    "code",
    "pre",
    "table",
    "th",
    "td",
)


# ---------- 编译器 ----------


def test_merge_config_fills_defaults():
    cfg = merge_config({"colors": {"primary": "#FF0000"}})
    assert cfg["colors"]["primary"] == "#FF0000"
    assert cfg["colors"]["text"] == DEFAULT_CONFIG["colors"]["text"]
    assert cfg["typography"]["bodySize"] == DEFAULT_CONFIG["typography"]["bodySize"]
    assert cfg["components"] == {}


def test_compile_styles_has_all_required_elements():
    styles = compile_styles()
    for key in REQUIRED_STYLE_KEYS:
        assert styles.get(key), f"缺少 {key} 样式"


def test_compile_styles_applies_colors_and_typography():
    styles = compile_styles(
        {
            "colors": {"primary": "#123456", "text": "#222222"},
            "typography": {
                "bodySize": "18px",
                "bodyLineHeight": "2.0",
                "heading1Size": "30px",
            },
        }
    )
    assert styles["paragraph"]["font-size"] == "18px"
    assert styles["paragraph"]["line-height"] == "2.0"
    assert styles["paragraph"]["color"] == "#222222"
    assert styles["h1"]["font-size"] == "30px"
    assert styles["h2"]["border-left"] == "4px solid #123456"
    assert styles["article"]["font-size"] == "18px"


def test_compile_styles_component_overrides_win():
    styles = compile_styles(
        {
            "components": {
                "paragraph": {"margin": "0 0 30px", "color": "#abcdef"},
                "h2": {"border-left": "none", "padding-left": "0"},
            }
        }
    )
    assert styles["paragraph"]["margin"] == "0 0 30px"
    assert styles["paragraph"]["color"] == "#abcdef"
    assert styles["h2"]["border-left"] == "none"
    assert styles["h2"]["padding-left"] == "0"
    # 未覆盖的字段保留编译默认值
    assert "font-size" in styles["h2"]


def test_compile_styles_ignores_unknown_component_and_bad_hex():
    styles = compile_styles(
        {
            "colors": {"primary": "not-a-color"},
            "components": {"no-such-component": {"color": "#000"}},
        }
    )
    # 非法颜色不抛错（保持发布链路健壮），直接原样使用
    assert styles["h2"]["border-left"] == "4px solid not-a-color"
    assert "no-such-component" not in styles


def test_tint_mixes_toward_white():
    assert tint("#000000", 1.0) == "#ffffff"
    assert tint("#000000", 0.0) == "#000000"
    assert tint("#2563EB", 0.5) == "#92b1f5"
    assert tint("nothex", 0.5) == "nothex"


# ---------- 内置主题 ----------


def test_five_builtin_themes_defined():
    ids = [t.id for t in BUILTIN_THEMES]
    assert len(BUILTIN_THEMES) >= 5
    assert len(ids) == len(set(ids))
    for theme in BUILTIN_THEMES:
        assert theme.is_builtin is True
        assert theme.name and theme.description
        for key in REQUIRED_STYLE_KEYS:
            assert theme.styles.get(key), f"{theme.id} 缺少 {key}"


def test_default_theme_unchanged():
    theme = get_theme()
    assert theme.id == DEFAULT_THEME_ID == "paperhub-science"
    assert theme.name == "PaperHub Science"


def test_builtin_configs_are_serializable():
    import json

    for theme in BUILTIN_THEMES:
        raw = json.dumps(theme.to_dict(), ensure_ascii=False)
        assert theme.id in raw
        # to_dict 支持再次 from_dict（JSON 主题扩展点）
        assert get_theme(theme.id).name == theme.name


# ---------- Pydantic 校验 ----------


def test_schema_rejects_bad_color():
    with pytest.raises(ValidationError):
        WeChatThemeConfig(colors={"primary": "red"})


def test_schema_rejects_bad_font_size():
    with pytest.raises(ValidationError):
        WeChatThemeConfig(typography={"bodySize": "big"})


def test_schema_accepts_unitless_line_height():
    cfg = WeChatThemeConfig(typography={"bodyLineHeight": "1.9"})
    assert cfg.typography.bodyLineHeight == "1.9"


def test_schema_requires_string_component_values():
    with pytest.raises(ValidationError):
        WeChatThemeConfig(components={"paragraph": {"margin": 12}})


# ---------- Renderer 组件 ----------

SAMPLE_MD = """# 一级标题

正文段落，包含 **加粗**、*斜体*、`行内代码` 与 [链接](https://example.com)。

## 二级标题

> 普通引用

> [!NOTE]
> Callout 提示内容

### 三级标题

- 列表项一
- 列表项二

| 指标 | 数值 |
| --- | --- |
| 准确率 | 91% |

```python
print("hi")
```

![Figure 1](https://example.com/a.png)

*图 1：示例图片说明*

---
"""


def test_renderer_outputs_every_component_with_inline_style():
    html = render_markdown_html(SAMPLE_MD, get_theme())
    assert "<h1" in html and "一级标题" in html
    assert "<h2" in html and "<h3" in html
    assert "<p" in html and "正文段落" in html
    assert "<blockquote" in html and "普通引用" in html
    assert "<section" in html and "Callout 提示内容" in html  # Callout
    assert "<img" in html and "示例图片说明" in html
    assert "<table" in html and "<th" in html and "<td" in html and "91%" in html
    assert "<code" in html and "<pre" in html
    assert "<hr" in html
    assert 'style="' in html


def test_renderer_is_wechat_compatible():
    html = render_markdown_html(SAMPLE_MD, get_theme())
    assert "<script" not in html
    assert "<link" not in html
    assert "<style" not in html
    assert "class=" not in html
    assert "javascript:" not in html
    assert "var(--" not in html  # 不使用 CSS 变量


def test_renderer_escapes_dangerous_markdown():
    html = render_markdown_html("<script>alert(1)</script>", get_theme())
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_renderer_theme_controls_callout_style():
    theme = get_theme()
    html = render_markdown_html("> [!WARNING]\n> 注意安全", theme)
    assert theme.styles["callout"]["background-color"] in html
    assert theme.styles["calloutTitle"]["color"] in html
    assert "警告" in html  # 未显式给标题时使用中文默认标题


def test_renderer_custom_title_in_callout():
    html = render_markdown_html("> [!TIP] 我的标题\n> 正文", get_theme())
    assert "我的标题" in html


def test_renderer_content_is_not_lost():
    md = "唯一标记A\n\n唯一标记B\n\n> 唯一标记C"
    html = render_markdown_html(md, get_theme())
    for marker in ("唯一标记A", "唯一标记B", "唯一标记C"):
        assert marker in html
