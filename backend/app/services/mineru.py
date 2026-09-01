"""MinerU 解析服务：接口 + Mock（PyMuPDF）+ 远程 API 实现。

真实实现调用 MinerU 官方 API；未配置时使用 MockMinerUService，
用 PyMuPDF 提取文本与内嵌图片，保证无 Key 也能跑通流程。
"""

from __future__ import annotations

import base64
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("mineru")


@dataclass
class ExtractedImage:
    name: str
    data: bytes
    page: int | None = None
    ext: str = "png"


@dataclass
class ParseResult:
    markdown: str = ""
    images: list[ExtractedImage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    source: str = "mock"


class MinerUService:
    """解析服务统一接口。"""

    async def parse_pdf(self, file_path: str | Path) -> ParseResult:
        raise NotImplementedError


class MockMinerUService(MinerUService):
    """基于 PyMuPDF 的本地解析（无需 API Key）。"""

    async def parse_pdf(self, file_path: str | Path) -> ParseResult:
        import fitz  # pymupdf

        path = Path(file_path)
        doc = fitz.open(str(path))
        md_parts: list[str] = []
        images: list[ExtractedImage] = []

        title = self._detect_title(doc) or path.stem
        md_parts.append(f"# {title}\n")
        md_parts.append("> 由 PaperHub MockMinerUService 解析（PyMuPDF）\n")

        for page_idx, page in enumerate(doc):
            text = page.get_text("text").strip()
            if text:
                md_parts.append(self._text_to_markdown(text, page_idx))
            for img_idx, img in enumerate(page.get_images(full=True)):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    data = pix.tobytes("png")
                    name = f"image_{page_idx + 1:03d}_{img_idx + 1:03d}.png"
                    images.append(
                        ExtractedImage(name=name, data=data, page=page_idx + 1)
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning("图片提取失败 page=%s: %s", page_idx, e)

        metadata = {
            "title": title,
            "pages": doc.page_count,
            "images": [i.name for i in images],
            "source": "mock-mineru",
        }
        doc.close()

        if images:
            md_parts.append("## Figures\n")
            for n, img in enumerate(images, start=1):
                md_parts.append(f"![Figure {n}](images/{img.name})")
                md_parts.append(f"\n*Figure {n}*")

        return ParseResult(
            markdown="\n\n".join(md_parts),
            images=images,
            metadata=metadata,
            source="mock",
        )

    @staticmethod
    def _detect_title(doc) -> str | None:
        for page_idx in range(min(2, doc.page_count)):
            text = doc[page_idx].get_text("text").strip()
            for ln in text.splitlines():
                ln = ln.strip()
                if 4 <= len(ln) <= 120 and len(ln.split()) >= 3 and not ln.isupper():
                    return ln
        return None

    @staticmethod
    def _text_to_markdown(text: str, page_idx: int) -> str:
        lines = [ln.rstrip() for ln in text.splitlines()]
        out: list[str] = []
        for ln in lines:
            if not ln.strip():
                continue
            if re.fullmatch(r"\s*\d+\s*", ln):  # 页码
                continue
            # 全大写短行视为标题
            if len(ln) < 80 and ln == ln.upper() and any(c.isalpha() for c in ln):
                out.append(f"\n### {ln.strip()}")
            elif re.match(
                r"^(\d+(\.\d+)*\s+)?(Abstract|Introduction|Method|Results|Discussion|Conclusion|References|Acknowledg)\w*\b",
                ln,
                re.I,
            ):
                out.append(f"\n### {ln.strip()}")
            else:
                out.append(ln)
        return "\n\n".join(out)


class RemoteMinerUService(MinerUService):
    """调用 MinerU 官方 API。"""

    def __init__(self, api_url: str, api_key: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def parse_pdf(self, file_path: str | Path) -> ParseResult:
        path = Path(file_path)
        with open(path, "rb") as f:
            content = f.read()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=300) as client:
            # 通用上传端点，具体路径由 MINERU_API_URL 决定
            resp = await client.post(
                f"{self.api_url}/parse",
                headers=headers,
                files={"file": (path.name, content, "application/pdf")},
            )
            resp.raise_for_status()
            data = resp.json()
        images: list[ExtractedImage] = []
        for img in data.get("images", []):
            b64 = img.get("data") or img.get("base64")
            if b64:
                images.append(
                    ExtractedImage(
                        name=img.get("name", f"img_{uuid.uuid4().hex[:8]}.png"),
                        data=base64.b64decode(b64),
                    )
                )
        return ParseResult(
            markdown=data.get("markdown") or data.get("content_md") or "",
            images=images,
            metadata=data.get("metadata") or {},
            source="remote",
        )


def get_mineru_service() -> MinerUService:
    if settings.mineru_api_url and settings.mineru_api_key:
        return RemoteMinerUService(settings.mineru_api_url, settings.mineru_api_key)
    return MockMinerUService()
