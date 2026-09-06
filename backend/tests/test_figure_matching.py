"""YOLO Figure 与 Markdown 位置匹配（文字层编号锚定）测试。"""

from types import SimpleNamespace

from app.services.figures import (
    caption_number,
    extract_caption,
    extract_caption_number,
    match_figures_to_markdown,
    text_lines_from_words,
)


# ---------- caption_number：从图注文本提取编号 ----------


def test_caption_number_plain_english():
    assert caption_number("Fig. 1 Overview of the research framework.") == 1


def test_caption_number_upper_without_dot():
    assert caption_number("FIGURE 12 Modeling results.") == 12


def test_caption_number_chinese():
    assert caption_number("图3 实验装置示意图。") == 3


def test_caption_number_body_reference_returns_digit():
    assert caption_number("The results are shown in (Fig. 2B).") == 2


def test_caption_number_none_without_figure_word():
    assert caption_number("Training loss curves of models.") is None


# ---------- extract_caption_number：定位图注所在行并提取编号 ----------

BOX = [75, 43, 528, 329]  # 对应页面上 YOLO 检出的 bbox（PDF 坐标）


def _line(x0, y0, x1, y1, text):
    return (x0, y0, x1, y1, text)


def test_extract_picks_caption_at_bbox_top_within_gap():
    lines = [
        _line(75, 60, 500, 80, "Fig. 1 Overview of the research framework."),
        _line(75, 85, 500, 105, "sizes (Fig. 1B). We employ surface tension"),
        _line(75, 110, 500, 130, "criteria (Fig. 1E). Through this computational"),
    ]
    assert extract_caption_number(lines, BOX) == 1


def test_extract_picks_caption_below_bbox():
    lines = [
        _line(75, 100, 500, 120, "The framework overview precedes the figure."),
        _line(75, 340, 500, 360, "Fig. 2 Results of stable interface formation."),
    ]
    assert extract_caption_number(lines, BOX) == 2


def test_extract_prefers_caption_line_over_body_reference():
    lines = [
        _line(75, 44, 500, 62, "Fig. 7 Overview."),
        _line(75, 310, 500, 330, "shown in (Fig. 9C)."),
    ]
    assert extract_caption_number(lines, BOX) == 7


def test_extract_returns_none_when_only_body_reference_near_box():
    lines = [_line(75, 310, 500, 330, "shown in (Fig. 9C).")]
    assert extract_caption_number(lines, BOX) is None


def test_extract_returns_none_when_caption_far_away():
    lines = [_line(75, 500, 500, 520, "Fig. 9 far away from the figure box.")]
    assert extract_caption_number(lines, BOX) is None


def test_extract_ignores_lines_without_horizontal_overlap():
    lines = [
        _line(900, 44, 1100, 62, "Fig. 3 Other column caption."),
        _line(75, 344, 500, 362, "Fig. 4 Real caption below the box."),
    ]
    assert extract_caption_number(lines, BOX) == 4


def test_extract_caption_returns_number_and_line_text():
    lines = [
        _line(75, 60, 500, 80, "Fig. 1 Overview of the research framework."),
        _line(75, 85, 500, 105, "sizes (Fig. 1B). We employ surface tension"),
    ]
    assert extract_caption(lines, BOX) == (
        1,
        "Fig. 1 Overview of the research framework.",
    )


def test_extract_caption_none_when_no_caption():
    lines = [_line(75, 500, 500, 520, "Fig. 9 far away.")]
    assert extract_caption(lines, BOX) == (None, None)


def test_text_lines_from_words_groups_by_block_and_line():
    words = [
        (75.0, 60.0, 100.0, 72.0, "Fig.", 1, 1, 0),
        (105.0, 60.0, 130.0, 72.0, "1", 1, 1, 1),
        (75.0, 85.0, 100.0, 97.0, "Some", 1, 2, 0),
        (75.0, 60.0, 100.0, 72.0, "Fig.", 2, 1, 0),
    ]
    lines = text_lines_from_words(words)
    assert (75.0, 60.0, 130.0, 72.0, "Fig. 1") in lines
    assert (75.0, 85.0, 100.0, 97.0, "Some") in lines
    assert (75.0, 60.0, 100.0, 72.0, "Fig.") in lines


def test_text_lines_from_words_merges_same_row_fragments():
    words = [
        (42.5, 333.3, 61.0, 340.8, "Fig. 1", 1, 1, 0),
        (68.0, 333.4, 552.8, 340.9, "Overview of the research framework.", 2, 1, 0),
        (42.5, 343.3, 552.7, 350.8, "the center channel. (B) Dimensions", 3, 1, 0),
    ]
    lines = text_lines_from_words(words)
    assert (42.5, 333.3, 552.8, 340.9, "Fig. 1 Overview of the research framework.") in lines
    assert extract_caption_number(lines, BOX) == 1


# ---------- match_figures_to_markdown：正文引用重写 ----------

MD = (
    "## 3 Method\n\n"
    "text text.\n\n"
    "![](images/a1.jpg)\n"
    "Fig. 1 Overview of the research framework.\n\n"
    "![](images/b2.jpg)\n"
    "Fig. 2 Results of stable interface formation.\n\n"
    "![](images/c3.jpg)\n"
    "Fig. 3 Ablation study of each module.\n\n"
    "![](images/cover.jpg)\n"
    "Showcasing research from a laboratory, no figure number here.\n"
)


def _fig(n, path):
    return SimpleNamespace(figure_number=n, image_path=path, id=f"id{n}")


def test_match_replaces_matched_refs_and_keeps_others():
    figs = [
        _fig(1, "paper1/figures/page3_fig1.png"),
        _fig(2, "paper1/figures/page4_fig2.png"),
    ]
    out = match_figures_to_markdown(MD, figs)
    assert "![](figures/page3_fig1.png)" in out
    assert "![](figures/page4_fig2.png)" in out
    assert "![](images/c3.jpg)" in out  # 未检出 Figure 3 -> 保留 MinerU 原图
    assert "![](images/cover.jpg)" not in out  # 无编号的非正文图 -> 移除
    assert "![](images/a1.jpg)" not in out


def test_match_same_number_panels_pair_in_order():
    md = (
        "![](images/a1.jpg)\n"
        "Fig. 2 Panel arrangement of the chip.\n\n"
        "![](images/b2b.jpg)\n"
        "Fig. 2 Panel arrangement of the chip.\n"
    )
    figs = [
        _fig(2, "paper1/figures/page4_fig2.png"),
        _fig(2, "paper1/figures/page5_fig2b.png"),
    ]
    out = match_figures_to_markdown(md, figs)
    assert "![](figures/page4_fig2.png)" in out
    assert "![](figures/page5_fig2b.png)" in out


def test_match_ignores_md_mode_figures():
    figs = [_fig(1, "paper1/images/abc123.jpg")]
    out = match_figures_to_markdown(MD, figs)
    assert "![](images/a1.jpg)" in out  # 无 YOLO 记录，正文图 -> MinerU 原图
    assert "![](images/cover.jpg)" not in out  # 非正文图 ->> 不渲染
    assert "figures/" not in out


def test_match_empty_figures_keeps_body_refs_and_drops_unnumbered():
    out = match_figures_to_markdown(MD, [])
    assert "![](images/a1.jpg)" in out  # 正文 Figure 1（未检出）-> MinerU 原图
    assert "![](images/cover.jpg)" not in out  # 非正文图 -> 不渲染
    assert "![](images/cover.jpg)" not in out
