"""基于 Markdown 的 Figure 解析。

MinerU 解析出的 markdown 按文档顺序内嵌了图片引用（images/xxx），
图注通常紧跟在图片引用之后的段落。这里从 markdown 还原出：
- 图片在正文中出现的顺序（与哈希随机排序无关）；
- 每张图片对应的图注文本。
"""

from __future__ import annotations

import re
from pathlib import Path

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".jfif",
    ".gif",
    ".bmp",
    ".webp",
    ".svg",
    ".tif",
    ".tiff",
}

_IMG_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
_CAPTION_MAX = 200
_CAPTION_SCAN_LINES = 15


def _is_local_image_target(target: str) -> bool:
    if not target.startswith("images/"):
        return False
    path = target.split("?", 1)[0]
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def _is_skip_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith(("#", "!", "<table", "</table", "<caption", "```")):
        return True
    if stripped.startswith("|"):
        return True
    if _IMG_LINK_RE.search(stripped):
        return True
    return False


def parse_figure_refs(markdown: str) -> list[dict]:
    """返回 markdown 中按出现顺序的 Figure 列表。

    每项形如 {"image": "<basename>", "caption": "<图注或 None>"}，
    重复（含不同子目录下的同名）图片只保留首次出现。
    """
    if not markdown:
        return []
    lines = markdown.splitlines()
    out: list[dict] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines):
        for m in _IMG_LINK_RE.finditer(line):
            target = m.group(1).strip()
            if not _is_local_image_target(target):
                continue
            basename = target.rsplit("/", 1)[-1]
            if basename in seen:
                continue
            seen.add(basename)
            out.append(
                {
                    "image": basename,
                    "caption": _caption_after(lines, idx + 1),
                }
            )
    return out


def _caption_after(lines: list[str], start: int) -> str | None:
    """从图片引用之后的正文中取第一段非空文字作为图注。"""
    scanned = 0
    for line in lines[start:]:
        if _is_skip_line(line):
            continue
        scanned += 1
        if scanned > _CAPTION_SCAN_LINES:
            break
        text = " ".join(line.strip().split())
        if not text:
            continue
        return text[:_CAPTION_MAX].strip() or None
    return None


def group_figure_numbers(captions: list[str | None]) -> list[int]:
    """把连续相同图注（同一 Figure 的多幅子图）归为同一个 Figure 编号。"""
    numbers: list[int] = []
    counter = 0
    prev: str | None = None
    for cap in captions:
        text = (cap or "").strip()
        if text and text != prev:
            counter += 1
        elif not text:
            counter += 1
        prev = text
        numbers.append(counter)
    return numbers
