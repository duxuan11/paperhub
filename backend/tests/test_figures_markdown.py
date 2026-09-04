"""Figure 解析（基于 Markdown 中图片引用顺序/图注）测试。"""

from app.services.figures import group_figure_numbers, parse_figure_refs

MD = """# Title

text before figure.

![flow](images/figure1_a.png)
FIGURE 1 Overall workflow of the proposed method: (a) data, (b) model.

## Results

![loss](images/loss.png)
Training loss curves of models.

![external](https://example.com/x.png)

![panel2](images/figure1_b.png)
"""


def test_parse_figure_refs_returns_md_order_ignores_external():
    refs = parse_figure_refs(MD)
    assert [r["image"] for r in refs] == [
        "figure1_a.png",
        "loss.png",
        "figure1_b.png",
    ]


def test_parse_figure_refs_extracts_captions():
    refs = parse_figure_refs(MD)
    by_name = {r["image"]: r["caption"] for r in refs}
    assert by_name["figure1_a.png"].startswith("FIGURE 1 Overall workflow")
    assert by_name["loss.png"] == "Training loss curves of models."


def test_parse_figure_refs_image_without_following_text_has_no_caption():
    refs = parse_figure_refs(MD)
    by_name = {r["image"]: r["caption"] for r in refs}
    assert by_name["figure1_b.png"] in (None, "")


def test_parse_figure_refs_empty_markdown():
    assert parse_figure_refs("") == []


def test_parse_figure_refs_dedupes_same_basename_from_nested_paths():
    md = "![a](images/sub/dup.png)\n\nCaption A\n\n![b](images/dup.png)\n\nCaption B\n"
    refs = parse_figure_refs(md)
    assert len(refs) == 1
    assert refs[0]["image"] == "dup.png"
    assert refs[0]["caption"] == "Caption A"


def test_group_figure_numbers_keeps_same_caption_panels_together():
    caps = [
        "FIGURE 1 ...",
        "Construction ...",
        "Training loss curves ...",
        "Training loss curves ...",
        "Training loss curves ...",
        "FIGURE 5 ...",
        "Evaluation of metric ...",
        "Evaluation of metric ...",
    ]
    nums = group_figure_numbers(caps)
    assert nums == [1, 2, 3, 3, 3, 4, 5, 5]


def test_group_figure_numbers_none_caption_is_own_number():
    assert group_figure_numbers(["A", None, "B"]) == [1, 2, 3]
