"""PDF 整页渲染 / 区域裁剪（供 YOLO Figure 检测使用）测试。"""

import tempfile
from pathlib import Path

from app.services.yolo import crop_page_png, render_pdf_pages

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


class _Box:
    def __init__(self, conf, cls, xyxy):
        self.conf = [conf]
        self.cls = [cls]
        self.xyxy = [_Row(xyxy)]


class _Row:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class _Results:
    def __init__(self, boxes):
        self.boxes = boxes


class _FakeModel:
    names = {0: "figure", 1: "table"}

    def __init__(self, per_page):
        self.per_page = per_page

    def predict(self, path, **kw):
        import os
        import re

        n = int(re.search(r"page_(\d+)", os.path.basename(path)).group(1))
        return [_Results(self.per_page.get(n, []))]


def test_detect_pages_selects_highest_conf_box_and_maps_class():
    from app.services.yolo import UltralyticsYoloService

    model = _FakeModel(
        {
            1: [
                _Box(0.4, 0, [1, 1, 10, 10]),
                _Box(0.9, 1, [2, 2, 12, 12]),
            ]
        }
    )
    svc = UltralyticsYoloService("fake.pt")
    svc._model = model

    async def go():
        return await svc.detect_pages([("/tmp/page_001.png", 1)])

    import asyncio

    out = asyncio.run(go())
    assert len(out) == 1
    assert out[0].type == "table"
    assert out[0].bbox == [2, 2, 12, 12]
    assert out[0].page == 1


def test_detect_pages_skips_page_without_detections():
    from app.services.yolo import UltralyticsYoloService

    svc = UltralyticsYoloService("fake.pt")
    svc._model = _FakeModel({})
    import asyncio

    out = asyncio.run(svc.detect_pages([("/tmp/page_001.png", 1)]))
    assert out == []
