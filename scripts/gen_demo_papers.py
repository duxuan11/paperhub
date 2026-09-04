#!/usr/bin/env python3
"""生成 demo 论文 PDF（含文本 + 内嵌 Figure 图片），用于无 Key 演示。

用法: cd backend && uv run python ../scripts/gen_demo_papers.py
"""

from __future__ import annotations

import io
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "demo"
DEMO_DIR.mkdir(exist_ok=True)


def make_chart_png(style: str, n: int = 6) -> bytes:
    """用 fitz 绘制简单柱状图/折线图，返回 PNG 字节。"""
    W, H = 600, 360
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, W, H), True)
    pix.clear_with(255)  # 白底
    # 转成可绘制的 pdf 页面来画
    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    # 坐标轴
    page.draw_line(
        fitz.Point(50, 300), fitz.Point(550, 300), color=(0.2, 0.2, 0.2), width=1.5
    )
    page.draw_line(
        fitz.Point(50, 40), fitz.Point(50, 300), color=(0.2, 0.2, 0.2), width=1.5
    )
    import random

    random.seed(42)
    labels = ["A", "B", "C", "D", "E", "F"]
    for i in range(n):
        v = random.randint(30, 250)
        x0 = 70 + i * 80
        if style == "bar":
            page.draw_rect(
                fitz.Rect(x0, 300 - v, x0 + 40, 300),
                color=(0.2, 0.4, 0.9),
                fill=(0.3, 0.5, 0.9),
            )
        else:
            x = x0 + 20
            if i > 0:
                prev = random.randint(30, 250)
                page.draw_line(
                    fitz.Point(x - 80, 300 - prev),
                    fitz.Point(x, 300 - v),
                    color=(0.9, 0.3, 0.3),
                    width=2,
                )
            page.draw_circle(
                fitz.Point(x, 300 - v), 5, color=(0.9, 0.3, 0.3), fill=(0.9, 0.3, 0.3)
            )
        page.insert_text(fitz.Point(x0 + 5, 320), labels[i], color=(0, 0, 0))
    page.insert_text(
        fitz.Point(240, 340), f"{style.capitalize()} result", color=(0, 0, 0)
    )
    # 渲染为 pixmap 再导出 PNG
    mat = fitz.Matrix(1, 1)
    pm = page.get_pixmap(matrix=mat, alpha=False)
    png = pm.tobytes("png")
    doc.close()
    return png


def add_figure(page, png: bytes, number: int, caption: str, y: float) -> float:
    rect = fitz.Rect(80, y, 520, y + 240)
    page.insert_image(rect, stream=png)
    page.insert_text(
        fitz.Point(80, y + 256),
        f"Figure {number}: {caption}",
        fontsize=10,
        fontname="helv",
        color=(0.1, 0.1, 0.1),
    )
    return y + 270


def build_paper(path: Path, title: str, authors: str) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    state = {"y": 60.0}

    def text(p, txt, size=11, fontname="helv", bold=False, y=None, x=72):
        fn = "hebo" if bold else fontname
        if y is None:
            y = state["y"] + size * 1.3
        p.insert_text(fitz.Point(x, y), txt, fontsize=size, fontname=fn)
        state["y"] = y
        return y

    y = text(page, title, size=18, bold=True)
    y = text(page, authors, size=11) + 4
    y = (
        text(
            page,
            "Department of Computer Science, Example University, Beijing, China",
            size=9,
        )
        + 6
    )
    y = text(page, "Abstract", size=13, bold=True, y=y + 8)
    abstract = (
        "Deep learning has advanced scientific research across many domains. "
        "In this paper, we propose a novel method for scientific document understanding, "
        "combining layout analysis with multimodal representation learning. "
        "We conduct extensive experiments on three benchmark datasets and demonstrate "
        "consistent improvements over strong baselines."
    )
    for line in _wrap(abstract, 90):
        y = text(page, line, size=10, y=y + 12)

    sections = [
        (
            "1 Introduction",
            [
                "Scientific papers are a primary medium for knowledge dissemination.",
                "However, extracting structured information from PDF documents remains challenging.",
                "We address this problem with a unified framework described below.",
            ],
        ),
        (
            "2 Related Work",
            [
                "Prior work includes rule-based document parsers and end-to-end neural models.",
                "Our method builds upon these ideas while introducing several novel components.",
            ],
        ),
        (
            "3 Method",
            [
                "Our framework consists of three stages: (1) layout detection, (2) figure extraction,",
                "and (3) content reasoning. We use a transformer backbone to encode visual regions.",
                "The loss function is defined as L = L_cls + lambda * L_reg.",
            ],
        ),
        (
            "4 Experiments",
            [
                "We evaluate on PubTabNet, DocBank and our internal corpus.",
                "Our model achieves state-of-the-art accuracy on all three benchmarks.",
            ],
        ),
        (
            "5 Conclusion",
            [
                "We present an effective approach to scientific document understanding.",
                "Future work will explore cross-lingual and zero-shot settings.",
            ],
        ),
    ]
    for title_s, paras in sections:
        y = text(page, title_s, size=13, bold=True, y=y + 14)
        for line in paras:
            for wl in _wrap(line, 100):
                y = text(page, wl, size=10, y=y + 12)

    # 加入三张 Figure 图
    y = y + 10
    pngs = [make_chart_png("bar"), make_chart_png("line"), make_chart_png("bar")]
    captions = [
        "Comparison of overall accuracy on three benchmark datasets.",
        "Training loss curves of our model versus baselines.",
        "Ablation study on the effect of each module.",
    ]
    for i, (png, cap) in enumerate(zip(pngs, captions), start=1):
        if y > 640:
            page = doc.new_page(width=595, height=842)
            y = 60
            state["y"] = 60
        y = add_figure(page, png, i, cap, y)

    # References
    page = doc.new_page(width=595, height=842)
    state["y"] = 60
    y = text(page, "References", size=13, bold=True, y=60)
    refs = [
        "[1] Doe, J., & Smith, A. Document parsing with deep learning. Nature, 2026.",
        "[2] Zhang, L., et al. Layout-aware transformers. CVPR, 2025.",
        "[3] Wang, R. Scientific figure understanding. AAAI, 2024.",
    ]
    for r in refs:
        y = text(page, r, size=10, y=y + 12)

    doc.save(str(path))
    doc.close()
    print(f"生成: {path}")


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


if __name__ == "__main__":
    build_paper(
        DEMO_DIR / "paper.pdf",
        "A Unified Framework for Scientific Document Understanding",
        "Jane Doe, Li Zhang, Ming Wang",
    )
    build_paper(
        DEMO_DIR / "paper2.pdf",
        "Multimodal Figure Analysis for Research Papers",
        "Alice Chen, Bob Liu",
    )
    print("Done.")
