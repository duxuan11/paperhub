"""Figure 检测服务：接口 + 启发式 + Ultralytics YOLO（整页渲染检测）。

- YOLO 模式：把 PDF 每页渲染成图片，在整页图上检测 Figure 框并裁剪保存；
  未配置 YOLO 或检测为空时，使用 HeuristicFigureService 按 markdown 顺序取图，
  保证无模型也能跑通流程。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("yolo")

_RENDER_ZOOM = 2.0

RENDER_ZOOM = _RENDER_ZOOM


def render_pdf_pages(
    pdf_bytes: bytes, out_dir: str | Path, zoom: float = _RENDER_ZOOM
) -> list[tuple[str, int]]:
    """把 PDF 每页渲染为 PNG，返回 [(本地路径, 页码1-based), ...]。"""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    out: list[tuple[str, int]] = []
    try:
        matrix = fitz.Matrix(zoom, zoom)
        for pno in range(doc.page_count):
            pix = doc[pno].get_pixmap(matrix=matrix)
            path = Path(out_dir) / f"page_{pno + 1:03d}.png"
            pix.save(str(path))
            out.append((str(path), pno + 1))
    finally:
        doc.close()
    return out


def crop_page_png(
    pdf_bytes: bytes, page_index0: int, bbox_points: list[float]
) -> bytes:
    """按 PDF 坐标 bbox 裁剪某页区域为 PNG 字节。"""
    import fitz

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = doc[page_index0]
        clip = fitz.Rect(bbox_points)
        pix = page.get_pixmap(matrix=fitz.Matrix(_RENDER_ZOOM, _RENDER_ZOOM), clip=clip)
        return pix.tobytes("png")
    finally:
        doc.close()


@dataclass
class DetectedFigure:
    name: str
    image_path: str
    type: str = "figure"
    bbox: list | None = None
    page: int | None = None
    caption: str | None = None


class FigureDetectionService:
    async def detect(
        self, images: Sequence[tuple[str, int | None]]
    ) -> list[DetectedFigure]:
        """images: [(object_key, page), ...]"""
        raise NotImplementedError


class HeuristicFigureService(FigureDetectionService):
    """启发式：根据文件名/内容把 MinerU 图片归类为 figure。"""

    async def detect(
        self, images: Sequence[tuple[str, int | None]]
    ) -> list[DetectedFigure]:
        out: list[DetectedFigure] = []
        for i, (key, page) in enumerate(images, start=1):
            name = key.rsplit("/", 1)[-1]
            ftype = "figure"
            out.append(
                DetectedFigure(
                    name=name,
                    image_path=key,
                    type=ftype,
                    page=page,
                    caption=f"Figure {i}",
                )
            )
        return out


class UltralyticsYoloService(FigureDetectionService):
    """真实 YOLO 检测（需要 ultralytics + 权重文件）。"""

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as e:
                raise RuntimeError(
                    "未安装 ultralytics，请 pip install ultralytics"
                ) from e
            self._model = YOLO(self.model_path)
        return self._model

    async def detect_pages(
        self, pages: Sequence[tuple[str, int]]
    ) -> list[DetectedFigure]:
        """在整页渲染图上检测 Figure。

        pages: [(本地 PNG 路径, 页码1-based), ...]。bbox 为渲染图坐标系
        （像素），由调用方结合 zoom 换算为 PDF 坐标后裁剪保存。
        """
        model = self._load()
        names = getattr(model, "names", {})
        out: list[DetectedFigure] = []
        loop = asyncio.get_event_loop()
        for path, page in pages:
            results = await loop.run_in_executor(None, model.predict, path)
            best: tuple[float, int, list] | None = None
            for r in results:
                if r.boxes is None:
                    continue
                for box in r.boxes:
                    conf = float(box.conf[0])
                    if best is None or conf > best[0]:
                        best = (conf, int(box.cls[0]), box.xyxy[0].tolist())
            if best is None:
                continue
            _, cls_id, bbox = best
            out.append(
                DetectedFigure(
                    name=f"page{page}_fig{len(out) + 1}",
                    image_path="",
                    type=names.get(cls_id, "figure"),
                    bbox=bbox,
                    page=page,
                )
            )
        return out

    async def detect(
        self, images: Sequence[tuple[str, int | None]]
    ) -> list[DetectedFigure]:
        import io

        model = self._load()
        out: list[DetectedFigure] = []
        for key, page in images:
            from app.core.minio import storage

            data = storage.get_bytes(key)
            if not data:
                continue
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, model.predict, io.BytesIO(data))
            best = "figure"
            bbox = None
            for r in results:
                if r.boxes is not None and len(r.boxes) > 0:
                    cls_id = int(r.boxes.cls[0])
                    best = (
                        model.names.get(cls_id, "figure")
                        if hasattr(model, "names")
                        else "figure"
                    )
                    bbox = r.boxes.xyxy[0].tolist()
                    break
            name = key.rsplit("/", 1)[-1]
            out.append(
                DetectedFigure(
                    name=name, image_path=key, type=best, bbox=bbox, page=page
                )
            )
        return out


def get_figure_service() -> FigureDetectionService:
    if settings.yolo_enabled and settings.yolo_model_path:
        from pathlib import Path

        from app.core.config import ROOT

        model_path = settings.yolo_model_path
        if not Path(model_path).is_absolute():
            model_path = str(ROOT / model_path)
        return UltralyticsYoloService(model_path)
    return HeuristicFigureService()
