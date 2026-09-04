"""Markdown -> 微信公众号 HTML 格式化。

微信公众号图文消息的 content 字段接受 HTML（受白名单标签限制）。
这里做尽量安全的转换：标题、段落、列表、引用、代码、粗体、斜体、链接、图片。
"""

from __future__ import annotations

import html
import re

ALLOWED_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def escape(text: str) -> str:
    return html.escape(text, quote=False)


def _inline(text: str) -> str:
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = LINK_RE.sub(r'<a href="\2">\1</a>', text)
    return text


def markdown_to_wechat_html(md: str, image_map: dict[str, str] | None = None) -> str:
    """image_map: {占位名: 图片URL}，用于替换 ![](placeholder) 中的占位符。"""
    image_map = image_map or {}
    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    in_list = False
    list_tag = ""

    def close_list():
        nonlocal in_list, list_tag
        if in_list:
            out.append(f"</{list_tag}>")
            in_list = False

    for ln in lines:
        stripped = ln.strip()
        if stripped.startswith("```"):
            if in_code:
                out.append("</pre>")
                in_code = False
            else:
                close_list()
                out.append("<pre>")
                in_code = True
            continue
        if in_code:
            out.append(escape(ln))
            continue

        if not stripped:
            close_list()
            continue

        m = ALLOWED_IMG_RE.search(ln)
        if m:
            close_list()
            alt = m.group(1)
            src = m.group(2)
            src = image_map.get(src, src)
            out.append(f'<p><img src="{src}" alt="{escape(alt)}"></p>')
            continue

        if stripped.startswith("######"):
            close_list()
            out.append(f"<h6>{_inline(stripped[6:].strip())}</h6>")
        elif stripped.startswith("#####"):
            close_list()
            out.append(f"<h5>{_inline(stripped[5:].strip())}</h5>")
        elif stripped.startswith("####"):
            close_list()
            out.append(f"<h4>{_inline(stripped[4:].strip())}</h4>")
        elif stripped.startswith("###"):
            close_list()
            out.append(f"<h3>{_inline(stripped[3:].strip())}</h3>")
        elif stripped.startswith("##"):
            close_list()
            out.append(f"<h2>{_inline(stripped[2:].strip())}</h2>")
        elif stripped.startswith("# "):
            close_list()
            out.append(f"<h2>{_inline(stripped[2:].strip())}</h2>")
        elif stripped.startswith("> "):
            close_list()
            out.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list or list_tag != "ul":
                close_list()
                out.append("<ul>")
                in_list = True
                list_tag = "ul"
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        elif re.match(r"^\d+\.\s", stripped):
            if not in_list or list_tag != "ol":
                close_list()
                out.append("<ol>")
                in_list = True
                list_tag = "ol"
            out.append(f"<li>{_inline(re.sub(r'^\d+\.\s', '', stripped))}</li>")
        elif stripped.startswith("---"):
            close_list()
            out.append("<hr>")
        else:
            close_list()
            out.append(f"<p>{_inline(stripped)}</p>")

    close_list()
    if in_code:
        out.append("</pre>")
    return "\n".join(out)
