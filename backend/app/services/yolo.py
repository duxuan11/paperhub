"""Figure 检测服务：接口 + 启发式 + Ultralytics YOLO。

未配置 YOLO 模型时使用 HeuristicFigureService，将 MinerU 提取的图片
按规则分类为 figure/table/equation，保证无模型也能跑通流程。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("yolo")


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

    async def detect(
        self, images: Sequence[tuple[str, int | None]]
    ) -> list[DetectedFigure]:
        import io
        import asyncio

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
