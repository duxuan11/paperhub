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


# ---------- YOLO 图与正文位置匹配（PDF 文字层 <-> Markdown 引用） ----------

_CAPTION_RE = re.compile(r"(?i)(?:fig(?:ure)?\.?\s+|图\s*)([0-9]+)")
_CAPTION_AT_START_RE = re.compile(r"(?is)^\s*(?:fig(?:ure)?\.?|图)\s*[0-9]+")
_CAPTION_MAX_GAP = 25.0


def caption_number(text: str | None) -> int | None:
    """从图注文本中提取 Figure 编号（"Fig. 2B" -> 2、"图3" -> 3）。"""
    if not text:
        return None
    m = _CAPTION_RE.search(text)
    return int(m.group(1)) if m else None


def text_lines_from_words(words) -> list[tuple]:
    """把 PyMuPDF get_text("words") 词按 (block, line) 聚合为文本行。

    每行形如 (x0, y0, x1, y1, text)，坐标为 PDF 点数。
    同行不同 block 的相邻片段（如 "Fig. 1" 与图注正文分行存储）会合并为
    一个完整视觉行。
    """
    groups: dict[tuple[int, int], list[tuple]] = {}
    for x0, y0, x1, y1, word, block_no, line_no, _word_no in words:
        groups.setdefault((block_no, line_no), []).append((x0, y0, x1, y1, word))
    pieces: list[tuple] = []
    for _key, ws in sorted(groups.items()):
        x0 = min(w[0] for w in ws)
        y0 = min(w[1] for w in ws)
        x1 = max(w[2] for w in ws)
        y1 = max(w[3] for w in ws)
        ws_sorted = sorted(ws, key=lambda w: w[0])
        pieces.append((x0, y0, x1, y1, " ".join(w[4] for w in ws_sorted)))
    return _merge_row_fragments(pieces)


def _merge_row_fragments(pieces: list[tuple]) -> list[tuple]:
    """把处于同一行且横向相邻的文字片段合并为完整行。"""
    out: list[tuple] = []
    for x0, y0, x1, y1, text in sorted(pieces, key=lambda p: (p[1], p[0])):
        if out and _same_row(out[-1], (x0, y0, x1, y1)):
            px0, py0, px1, py1, ptext = out[-1]
            out[-1] = (
                min(px0, x0),
                min(py0, y0),
                max(px1, x1),
                max(py1, y1),
                f"{ptext} {text}".strip(),
            )
        else:
            out.append((x0, y0, x1, y1, text))
    return out


def _same_row(a: tuple, b: tuple) -> bool:
    """两个片段是否处于同一视觉行且水平相邻（间隔 ≤20pt）。"""
    ay0, ay1 = a[1], a[3]
    by0, by1 = b[1], b[3]
    overlap = min(ay1, by1) - max(ay0, by0)
    if overlap < 0.4 * min(ay1 - ay0, by1 - by0):
        return False
    a_x1 = a[2]
    b_x0 = b[0]
    return a_x1 - 5 <= b_x0 <= a_x1 + 20


def extract_caption_number(
    lines: list[tuple], bbox: list[float], max_gap: float = _CAPTION_MAX_GAP
) -> int | None:
    """在 bbox 附近（上/下缘 ±max_gap 且横向相交）找图注行并提取编号。"""
    best = _best_caption_line(lines, bbox, max_gap)
    return best[2] if best else None


def extract_caption(
    lines: list[tuple], bbox: list[float], max_gap: float = _CAPTION_MAX_GAP
) -> tuple[int | None, str | None]:
    """在 bbox 附近找图注行，返回 (编号, 图注行文本)。"""
    best = _best_caption_line(lines, bbox, max_gap)
    if not best:
        return (None, None)
    text = best[1][4]
    return (best[2], text[:_CAPTION_MAX])


def _best_caption_line(
    lines: list[tuple], bbox: list[float], max_gap: float = _CAPTION_MAX_GAP
) -> tuple | None:
    """找到 bbox 附近最优的图注行（只认以 "Fig/Figure/图" 开头的图注行）。"""
    x0, y0, x1, y1 = bbox
    best: tuple | None = None
    for line in lines:
        lx0, ly0, lx1, ly1, text = line
        if ly0 > y1 + max_gap or ly1 < y0 - max_gap:
            continue
        if not (lx0 < x1 and lx1 > x0):
            continue
        if not _CAPTION_AT_START_RE.match(text):
            continue
        m = _CAPTION_RE.search(text)
        if not m:
            continue
        n = int(m.group(1))
        if ly0 <= y1 and ly1 >= y0:
            dist = 0.0
        else:
            dist = min(abs(ly0 - y1), abs(ly1 - y0))
        key = (-dist, -ly0)
        if best is None or key > best[0]:
            best = (key, line, n)
    return best


_LINK_RE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")


def match_figures_to_markdown(markdown: str, figures) -> str:
    """把 markdown 中与 YOLO 图按编号匹配的图片引用替换为 YOLO 裁剪图。

    规则（md 只渲染正文 figure）：
    - 图注含编号（Fig. N / Figure N / 图N）的引用：有 YOLO 同编号图 ->
      替换为 figures/pageN_figM.png；未检出 -> 保留 MinerU 原图；
    - 无编号的引用（封面图/期刊衍生图等非正文图）-> 从正文移除。
    """
    if not markdown:
        return markdown
    usable = [
        f
        for f in figures
        if "/figures/" in (getattr(f, "image_path", "") or "")
    ]
    queues: dict[int, list[str]] = {}
    for f in usable:
        n = getattr(f, "figure_number", None)
        if n is None:
            continue
        queues.setdefault(int(n), []).append(
            "figures/" + f.image_path.rsplit("/", 1)[-1]
        )
    replacements: dict[str, str] = {}
    remove: set[str] = set()
    for ref in parse_figure_refs(markdown):
        n = caption_number(ref.get("caption"))
        if n is None:
            remove.add(ref["image"])
            continue
        if queues.get(n):
            replacements[ref["image"]] = queues[n].pop(0)
    if not replacements and not remove:
        return markdown

    def _sub(m: re.Match) -> str:
        target = m.group(2).strip()
        base = target.rsplit("/", 1)[-1]
        rep = replacements.get(base)
        if rep is not None:
            return m.group(1) + rep + m.group(3)
        if base in remove:
            return ""
        return m.group(0)

    return _LINK_RE.sub(_sub, markdown)
