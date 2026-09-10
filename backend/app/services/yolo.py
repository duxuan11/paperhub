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


def _parse_names(raw) -> dict[int, str]:
    """从 ONNX 元数据解析类别名（兼容 JSON 与 Python dict repr）。"""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {int(k): str(v).strip().lower() for k, v in raw.items()}
    import ast
    import json

    for parser in (json.loads, ast.literal_eval):
        try:
            data = parser(raw)
            if isinstance(data, dict):
                return {int(k): str(v).strip().lower() for k, v in data.items()}
        except Exception:  # noqa: BLE001
            continue
    return {}


class OnnxYoloService(FigureDetectionService):
    """用 onnxruntime 直接推理 YOLO 导出的 ONNX 模型（end2end，输出已含 NMS）。

    无需 ultralytics / torch。模型输入为 [1, 3, H, W] 的 float32 RGB 张量
    （0~1），输出为 [1, N, 6] = [x1, y1, x2, y2, conf, cls]（letterbox 坐标）。
    只保留 figure 类别且置信度 >= conf_threshold 的框。
    """

    def __init__(self, model_path: str, conf_threshold: float = 0.25) -> None:
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self._session = None
        self._input_name = "images"
        self._input_h = 1024
        self._input_w = 1024
        self._names: dict[int, str] = {}

    def _load(self):
        if self._session is None:
            try:
                import onnxruntime as ort
            except ImportError as e:
                raise RuntimeError(
                    "未安装 onnxruntime，请安装 onnxruntime>=1.18"
                ) from e
            self._session = ort.InferenceSession(
                self.model_path, providers=["CPUExecutionProvider"]
            )
            inp = self._session.get_inputs()[0]
            self._input_name = inp.name
            shape = inp.shape
            try:
                self._input_h, self._input_w = int(shape[2]), int(shape[3])
            except (TypeError, ValueError, IndexError):
                self._input_h = self._input_w = 1024
            meta = self._session.get_modelmeta()
            self._names = _parse_names(meta.custom_metadata_map.get("names"))
        return self._session

    def _preprocess(self, img_bgr):
        """letterbox 到模型输入尺寸，并转为 [1,3,H,W] float32 RGB (0~1)。"""
        import cv2
        import numpy as np

        h, w = img_bgr.shape[:2]
        r = min(self._input_w / w, self._input_h / h)
        new_w, new_h = int(round(w * r)), int(round(h * r))
        img = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        dw, dh = self._input_w - new_w, self._input_h - new_h
        top, bottom = int(round(dh / 2 - 0.1)), int(round(dh / 2 + 0.1))
        left, right = int(round(dw / 2 - 0.1)), int(round(dw / 2 + 0.1))
        img = cv2.copyMakeBorder(
            img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )
        img = img[..., ::-1].transpose((2, 0, 1))  # BGR -> RGB, HWC -> CHW
        img = np.ascontiguousarray(img, dtype=np.float32) / 255.0
        return img[None]

    def _postprocess(
        self, output, orig_h: int, orig_w: int
    ) -> list[list[float]]:
        """把 letterbox 坐标映射回原图，过滤类别与置信度。"""
        r = min(self._input_w / orig_w, self._input_h / orig_h)
        pad_x = (self._input_w - orig_w * r) / 2
        pad_y = (self._input_h - orig_h * r) / 2
        out: list[list[float]] = []
        for row in output[0]:
            x1, y1, x2, y2, conf, cls_id = (float(v) for v in row)
            if conf < self.conf_threshold:
                continue
            name = self._names.get(int(cls_id), "figure")
            if name != "figure":
                continue
            out.append(
                [
                    (x1 - pad_x) / r,
                    (y1 - pad_y) / r,
                    (x2 - pad_x) / r,
                    (y2 - pad_y) / r,
                ]
            )
        return out

    async def _detect_bgr(self, img_bgr, loop) -> list[list[float]]:
        import numpy as np

        tensor = self._preprocess(img_bgr)
        h, w = img_bgr.shape[:2]
        session = self._load()

        def _run():
            return session.run(None, {self._input_name: tensor})[0]

        output = await loop.run_in_executor(None, _run)
        return self._postprocess(np.asarray(output), h, w)

    async def detect_pages(
        self, pages: Sequence[tuple[str, int]]
    ) -> list[DetectedFigure]:
        """在整页渲染图上检测 Figure。

        pages: [(本地 PNG 路径, 页码1-based), ...]。bbox 为原图像素坐标系，
        由调用方结合 zoom 换算为 PDF 坐标后裁剪保存。
        """
        import cv2

        self._load()
        loop = asyncio.get_event_loop()
        out: list[DetectedFigure] = []
        for path, page in pages:
            img_bgr = cv2.imread(path)
            if img_bgr is None:
                continue
            for bbox in await self._detect_bgr(img_bgr, loop):
                out.append(
                    DetectedFigure(
                        name=f"page{page}_fig{len(out) + 1}",
                        image_path="",
                        type="figure",
                        bbox=bbox,
                        page=page,
                    )
                )
        return out

    async def detect(
        self, images: Sequence[tuple[str, int | None]]
    ) -> list[DetectedFigure]:
        """对 MinIO 中的图片逐张检测（兼容旧接口，当前主流程未使用）。"""
        import cv2
        import numpy as np

        self._load()
        loop = asyncio.get_event_loop()
        out: list[DetectedFigure] = []
        for key, page in images:
            from app.core.minio import storage

            data = storage.get_bytes(key)
            if not data:
                continue
            img_bgr = cv2.imdecode(
                np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR
            )
            if img_bgr is None:
                continue
            name = key.rsplit("/", 1)[-1]
            for bbox in await self._detect_bgr(img_bgr, loop):
                out.append(
                    DetectedFigure(
                        name=name, image_path=key, type="figure", bbox=bbox, page=page
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
        return OnnxYoloService(model_path)
    return HeuristicFigureService()
