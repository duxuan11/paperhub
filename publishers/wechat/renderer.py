"""Markdown -> 微信公众号 inline-style HTML 渲染器（Theme 驱动）。

微信公众号图文正文只接受受白名单限制的 HTML，且无法加载外部 CSS，
因此最终 HTML 必须把样式全部写进 ``style="..."``。本模块只做两件事：

1. 把 Markdown 解析成结构标签（h1~h6 / p / blockquote / ul / ol / li / hr /
   img / pre / table ...）；
2. 把 :class:`~publishers.wechat.themes.WeChatTheme` 中对应元素的样式渲染为
   inline style。

主题是纯数据，渲染逻辑与主题无关 —— 新增主题不需要改这里。
"""

from __future__ import annotations

import html
import re

from publishers.wechat.themes import DEFAULT_THEME_ID, WeChatTheme, get_theme

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
_UL_RE = re.compile(r"^[-*+]\s+")
_OL_RE = re.compile(r"^\d+\.\s+")
_IMG_LINE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
_IMG_INLINE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_ITALIC_LINE_RE = re.compile(r"^\*(?!\*)(.+?)\*$")
_UNDERSCORE_LINE_RE = re.compile(r"^_(.+?)_$")
_CAPTION_HINT_RE = re.compile(r"^(图|表|Figure|Table|Fig\.?)\s*\d*\s*[:：.．]?", re.I)


def escape(text: str) -> str:
    """转义文本节点的 HTML 特殊字符。"""
    return html.escape(text, quote=False)


def _attr(value: str) -> str:
    return html.escape(value, quote=True)


def _style_value(value: str) -> str:
    """转义 style 属性值中的 ``&`` 与 ``"``（不转义单引号，字体名用单引号即可）。"""
    return value.replace("&", "&amp;").replace('"', "&quot;")


def style_attr(style: dict[str, str] | None) -> str:
    """把样式 dict 渲染为 inline style 属性；空样式返回空串。

    值中的双引号会转义为 ``&quot;``，避免破坏 ``style="..."`` 属性
    （如字体名 ``"PingFang SC"``）。
    """
    if not style:
        return ""
    body = ";".join(
        f"{k}:{_style_value(v)}" for k, v in style.items() if v
    )
    return f' style="{body}"' if body else ""


def _tag(tag: str, content: str, style: dict[str, str] | None = None) -> str:
    return f"<{tag}{style_attr(style)}>{content}</{tag}>"


def _inline(text: str, theme: WeChatTheme, image_map: dict[str, str]) -> str:
    """行内元素：先转义，再依次处理图片/链接/加粗/斜体/行内代码。"""
    text = escape(text)
    text = _IMG_INLINE_RE.sub(
        lambda m: (
            f'<img src="{_attr(image_map.get(m.group(2), m.group(2)))}"'
            f' alt="{_attr(m.group(1))}"{style_attr(theme.css("image"))}>'
        ),
        text,
    )
    text = _LINK_RE.sub(
        lambda m: (
            f'<a href="{_attr(m.group(2))}"{style_attr(theme.css("link"))}>'
            f"{m.group(1)}</a>"
        ),
        text,
    )
    text = re.sub(
        r"\*\*(.+?)\*\*",
        lambda m: _tag("strong", m.group(1), theme.css("strong")),
        text,
    )
    text = re.sub(
        r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
        lambda m: _tag("em", m.group(1), theme.css("em")),
        text,
    )
    text = re.sub(
        r"`(.+?)`",
        lambda m: _tag("code", m.group(1), theme.css("code")),
        text,
    )
    return text


def _looks_like_caption(line: str) -> bool:
    if not line:
        return False
    if _ITALIC_LINE_RE.match(line) or _UNDERSCORE_LINE_RE.match(line):
        return True
    return bool(_CAPTION_HINT_RE.match(line))


def _strip_caption(line: str) -> str:
    m = _ITALIC_LINE_RE.match(line) or _UNDERSCORE_LINE_RE.match(line)
    return m.group(1) if m else line


def _render_table(
    lines: list[str], start: int, theme: WeChatTheme, image_map: dict[str, str]
) -> tuple[str, int]:
    """渲染 GFM 管道表格，返回 (html, 下一行索引)。"""

    def cells(row: str) -> list[str]:
        row = row.strip().strip("|")
        return [c.strip() for c in row.split("|")]

    header = cells(lines[start])
    i = start + 2
    body: list[list[str]] = []
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        body.append(cells(lines[i]))
        i += 1

    th_style = theme.css("th")
    td_style = theme.css("td")
    head_html = "".join(
        f"<th{style_attr(th_style)}>{_inline(c, theme, image_map)}</th>"
        for c in header
    )
    rows_html = []
    for row in body:
        tds = "".join(
            f"<td{style_attr(td_style)}>{_inline(c, theme, image_map)}</td>"
            for c in row
        )
        rows_html.append(f"<tr>{tds}</tr>")
    table = (
        f"<table{style_attr(theme.css('table'))}><thead><tr>{head_html}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
    )
    return table, i


def render_markdown_html(
    md: str,
    theme: WeChatTheme | None = None,
    image_map: dict[str, str] | None = None,
) -> str:
    """把 Markdown 渲染为带 inline style 的微信公众号 HTML。

    ``image_map``：``{占位名: 可访问 URL}``，用于替换 ``![]({{figure:N}})``
    里的占位符（例如替换为微信 mmbiz URL）。
    """
    theme = theme or get_theme(DEFAULT_THEME_ID)
    image_map = image_map or {}
    lines = md.splitlines()
    blocks: list[str] = []
    i = 0
    total = len(lines)

    while i < total:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        # 代码块
        if stripped.startswith("```"):
            i += 1
            code_lines: list[str] = []
            while i < total and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # 跳过结束围栏
            blocks.append(
                _tag("pre", escape("\n".join(code_lines)), theme.css("pre"))
            )
            continue

        # 标题
        m = _HEADING_RE.match(stripped)
        if m:
            level = min(len(m.group(1)), 6)
            key = f"h{level}"
            blocks.append(
                _tag(key, _inline(m.group(2).strip(), theme, image_map), theme.css(key))
            )
            i += 1
            continue

        # 分割线
        if _HR_RE.match(stripped):
            blocks.append(_tag("hr", "", theme.css("hr")))
            i += 1
            continue

        # 引用（合并连续行）
        if stripped.startswith(">"):
            quote: list[str] = []
            while i < total and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            body = "<br>".join(
                _inline(q, theme, image_map) for q in quote if q != ""
            )
            blocks.append(_tag("blockquote", body, theme.css("blockquote")))
            continue

        # 列表（有序 / 无序）
        if _UL_RE.match(stripped) or _OL_RE.match(stripped):
            ordered = bool(_OL_RE.match(stripped))
            pattern = _OL_RE if ordered else _UL_RE
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < total:
                s = lines[i].strip()
                mm = pattern.match(s)
                if not mm:
                    break
                items.append(_inline(s[mm.end():].strip(), theme, image_map))
                i += 1
            li = "".join(
                f"<li{style_attr(theme.css('li'))}>{item}</li>" for item in items
            )
            blocks.append(_tag(tag, li, theme.css(tag)))
            continue

        # 表格
        if (
            "|" in stripped
            and i + 1 < total
            and _TABLE_SEP_RE.match(lines[i + 1])
        ):
            table, i = _render_table(lines, i, theme, image_map)
            blocks.append(table)
            continue

        # 独占一行的图片（支持紧随其后的图片说明）
        img = _IMG_LINE_RE.match(stripped)
        if img:
            alt = img.group(1)
            src = image_map.get(img.group(2), img.group(2))
            blocks.append(
                _tag(
                    "p",
                    f'<img src="{_attr(src)}" alt="{_attr(alt)}"'
                    f'{style_attr(theme.css("image"))}>',
                    {"margin": "0"},
                )
            )
            i += 1
            # 图片说明：允许与图片之间隔空行（LLM 常见输出）
            j = i
            while j < total and not lines[j].strip():
                j += 1
            if j < total and _looks_like_caption(lines[j].strip()):
                caption = _strip_caption(lines[j].strip())
                blocks.append(
                    _tag(
                        "p",
                        _inline(caption, theme, image_map),
                        theme.css("caption"),
                    )
                )
                i = j + 1
            continue

        # 普通段落
        blocks.append(
            _tag("p", _inline(stripped, theme, image_map), theme.css("paragraph"))
        )
        i += 1

    body = "\n".join(blocks)
    # 兜底：未被 Markdown 图片语法包起来的 {{figure:N}} 占位符也要替换，避免把
    # 字面量发到公众号正文里。
    for placeholder, url in image_map.items():
        if placeholder in body:
            body = body.replace(placeholder, _attr(url))
    return _tag("section", body, theme.css("article"))
