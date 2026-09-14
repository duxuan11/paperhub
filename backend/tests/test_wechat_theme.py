"""微信公众号主题（Theme）与封面配置测试（无需数据库 / Redis / 真实微信接口）。

覆盖：
1. Theme 注册表：默认主题存在、未知 id 回退默认、可注册新主题（可扩展）
2. 渲染器：正文 HTML 全部使用 inline style，不含 <style>/class，不依赖外部 CSS
3. 主题确实控制各类元素样式（标题/正文/引用/图片/图片说明/列表/分割线/链接）
4. build_article_payload 使用指定 Theme，并支持 author 覆盖
5. 封面优先级：文章显式封面 > 首图 > 内置默认封面
"""

import pytest
from app.core.config import settings  # noqa: F401  —— 注册仓库根目录到 sys.path

from publishers.wechat.publisher import build_article_payload
from publishers.wechat.renderer import render_markdown_html
from publishers.wechat.themes import (
    DEFAULT_THEME_ID,
    WeChatTheme,
    get_theme,
    list_themes,
    register_theme,
)

REQUIRED_STYLE_KEYS = (
    "article",
    "h1",
    "h2",
    "h3",
    "paragraph",
    "blockquote",
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
)


# ---------- 主题注册表 ----------


def test_default_theme_is_paperhub_science():
    theme = get_theme()
    assert theme.id == DEFAULT_THEME_ID == "paperhub-science"
    assert theme.name == "PaperHub Science"
    assert theme.description


def test_default_theme_controls_all_required_elements():
    styles = get_theme().styles
    for key in REQUIRED_STYLE_KEYS:
        assert styles.get(key), f"默认主题缺少 {key} 样式"


def test_unknown_theme_falls_back_to_default():
    assert get_theme("no-such-theme").id == DEFAULT_THEME_ID
    assert get_theme(None).id == DEFAULT_THEME_ID


def test_list_themes_contains_default():
    ids = [t.id for t in list_themes()]
    assert DEFAULT_THEME_ID in ids


def test_register_theme_is_extensible():
    theme = WeChatTheme(
        id="test-extra",
        name="Test Extra",
        description="第二套主题",
        styles={"paragraph": {"color": "#123456"}},
    )
    register_theme(theme)
    assert get_theme("test-extra").name == "Test Extra"
    assert "test-extra" in [t.id for t in list_themes()]


def test_theme_to_dict_roundtrip_shape():
    data = get_theme().to_dict()
    assert set(["id", "name", "description", "styles"]).issubset(data.keys())
    assert isinstance(data["styles"]["paragraph"], dict)


# ---------- 渲染器：inline style ----------

SAMPLE_MD = """# 一级标题

> 导语引用

## 二级标题

### 三级标题

正文段落，包含 **加粗**、*斜体*、`行内代码` 与 [链接](https://example.com)。

- 列表项一
- 列表项二

1. 有序一
2. 有序二

![Figure 1]({{figure:0}})

*图 1：示例图片说明*

---

```
code block
```
"""


def test_renderer_outputs_inline_styles_only():
    html = render_markdown_html(SAMPLE_MD, get_theme())
    assert "<style" not in html
    assert "class=" not in html
    assert "stylesheet" not in html
    assert 'style="' in html


def test_renderer_applies_default_theme_values():
    theme = get_theme()
    html = render_markdown_html(SAMPLE_MD, theme)
    # 标题、正文、引用、链接、分割线、图片、图片说明都要带上主题样式
    for key in ("h1", "h2", "h3", "paragraph", "blockquote", "link", "hr", "image", "caption"):
        style = theme.styles[key]
        marker = list(style.values())[0]
        assert marker in html, f"{key} 样式未出现在渲染结果中"


def test_renderer_caption_uses_caption_style():
    theme = get_theme()
    html = render_markdown_html("![Figure 1](http://img)\n\n*图 1：说明*", theme)
    caption_color = theme.styles["caption"]["color"]
    assert "图 1：说明" in html
    assert caption_color in html


def test_renderer_applies_custom_theme():
    register_theme(
        WeChatTheme(
            id="test-color",
            name="Color",
            styles={
                "h2": {"color": "#ff00aa"},
                "paragraph": {"color": "#00ff00"},
            },
        )
    )
    html = render_markdown_html("## 二级\n\n段落", get_theme("test-color"))
    assert "#ff00aa" in html
    assert "#00ff00" in html


def test_renderer_replaces_image_map():
    html = render_markdown_html(
        "![a]({{figure:0}})", get_theme(), {"{{figure:0}}": "https://mmbiz/x.png"}
    )
    assert 'src="https://mmbiz/x.png"' in html
    assert "{{figure" not in html


def test_renderer_escapes_html():
    html = render_markdown_html("<script>alert(1)</script>", get_theme())
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_renderer_escapes_quotes_in_style_values():
    """主题样式值里的双引号必须转义，否则会提前闭合 style="..." 属性。"""
    register_theme(
        WeChatTheme(
            id="test-quotes",
            name="Quotes",
            styles={"paragraph": {"font-family": '"X",sans-serif'}},
        )
    )
    html = render_markdown_html("正文", get_theme("test-quotes"))
    assert 'font-family:&quot;X&quot;,sans-serif' in html
    assert 'style="font-family:"X",sans-serif"' not in html


# ---------- payload ----------


def test_payload_uses_requested_theme():
    register_theme(
        WeChatTheme(
            id="test-payload",
            name="Payload",
            styles={"paragraph": {"color": "#abcdef"}},
        )
    )
    payload = build_article_payload("标题", "正文", theme="test-payload")
    assert "#abcdef" in payload["content"]


def test_payload_defaults_to_default_theme():
    payload = build_article_payload("标题", "正文")
    assert get_theme().styles["paragraph"]["color"] in payload["content"]


def test_payload_author_default_and_override():
    assert build_article_payload("标题", "正文")["author"] == "PaperHub"
    assert build_article_payload("标题", "正文", author="张三")["author"] == "张三"


def test_payload_unknown_theme_falls_back():
    payload = build_article_payload("标题", "正文", theme="ghost")
    assert get_theme().styles["paragraph"]["color"] in payload["content"]


# ---------- 封面选择 ----------


def test_cover_source_prefers_explicit_cover(monkeypatch):
    from app.workers import tasks

    blobs = {"paper/cover.png": b"COVER", "paper/fig1.png": b"FIG"}
    monkeypatch.setattr(tasks.storage, "get_bytes", lambda k: blobs.get(k))
    assert tasks._cover_source(["paper/fig1.png"], "paper/cover.png") == (
        b"COVER",
        "cover.png",
    )


def test_cover_source_falls_back_to_first_image(monkeypatch):
    from app.workers import tasks

    blobs = {"paper/fig1.png": b"FIG"}
    monkeypatch.setattr(tasks.storage, "get_bytes", lambda k: blobs.get(k))
    assert tasks._cover_source(["paper/fig1.png"], None) == (b"FIG", "fig1.png")


def test_cover_source_falls_back_to_default(monkeypatch):
    from app.workers import tasks

    monkeypatch.setattr(tasks.storage, "get_bytes", lambda k: None)
    data, name = tasks._cover_source([], None)
    assert data.startswith(b"\x89PNG")
    assert name.endswith(".png")


def test_cover_source_ignores_missing_explicit_cover(monkeypatch):
    from app.workers import tasks

    blobs = {"paper/fig1.png": b"FIG"}
    monkeypatch.setattr(tasks.storage, "get_bytes", lambda k: blobs.get(k))
    assert tasks._cover_source(["paper/fig1.png"], "paper/gone.png") == (
        b"FIG",
        "fig1.png",
    )


@pytest.mark.parametrize("theme_id", [None, "", "paperhub-science", "ghost"])
def test_get_theme_never_raises(theme_id):
    assert get_theme(theme_id).id == DEFAULT_THEME_ID
