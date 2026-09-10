"""PDF 整页渲染 / 区域裁剪 / ONNX YOLO 后处理（Figure 检测）测试。"""

import tempfile
from pathlib import Path

from app.services.yolo import (
    OnnxYoloService,
    _parse_names,
    crop_page_png,
    render_pdf_pages,
)

DEMO = Path(__file__).resolve().parents[2] / "demo" / "paper.pdf"
PDF = DEMO.read_bytes()


def test_render_pdf_pages_writes_png_per_page():
    with tempfile.TemporaryDirectory() as td:
        pages = render_pdf_pages(PDF, td, zoom=2.0)
        assert len(pages) >= 1
        path, page = pages[0]
        assert page == 1
        assert Path(path).exists()
        assert Path(path).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_crop_page_returns_png_bytes():
    data = crop_page_png(PDF, 0, [0, 0, 200, 200])
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 0


def _make_service():
    svc = OnnxYoloService("fake.onnx")
    svc._names = {0: "figure", 1: "title"}
    svc._input_h = 1024
    svc._input_w = 1024
    return svc


def test_parse_names_json_and_dict_repr():
    assert _parse_names('{"0": "figure", "1": "title"}') == {0: "figure", 1: "title"}
    assert _parse_names("{0: 'figure', 1: 'title'}") == {0: "figure", 1: "title"}
    assert _parse_names({0: "Figure", 1: "Title"}) == {0: "figure", 1: "title"}
    assert _parse_names(None) == {}


def test_postprocess_keeps_figure_and_filters_title_and_low_conf():
    svc = _make_service()
    output = [
        [
            [100, 100, 200, 200, 0.9, 0],  # figure，保留
            [300, 300, 400, 400, 0.8, 1],  # title，跳过
            [50, 50, 60, 60, 0.1, 0],  # figure 但低置信度，跳过
        ]
    ]
    boxes = svc._postprocess(output, orig_h=512, orig_w=512)
    assert len(boxes) == 1
    # 512x512 -> r=2.0，无 padding -> 坐标除以 2
    assert boxes[0] == [50.0, 50.0, 100.0, 100.0]


def test_postprocess_maps_back_from_letterbox_with_padding():
    svc = _make_service()
    # 原图 100x200 (h=100, w=200)，输入 1024x1024
    # r = min(1024/200, 1024/100) = 5.12
    # pad_y = (1024 - 100*5.12)/2 = 256
    output = [[[0, 256, 1024, 768, 0.9, 0]]]
    boxes = svc._postprocess(output, orig_h=100, orig_w=200)
    assert len(boxes) == 1
    x1, y1, x2, y2 = boxes[0]
    assert abs(x1) < 1e-4
    assert abs(y1) < 1e-4
    assert abs(x2 - 200) < 1e-4
    assert abs(y2 - 100) < 1e-4


def test_postprocess_empty_when_no_boxes():
    svc = _make_service()
    assert svc._postprocess([[]], 512, 512) == []
