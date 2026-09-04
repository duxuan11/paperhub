"""MinerU 解析服务：接口 + Mock（PyMuPDF）+ 远程 API 实现。

真实实现遵循 mineru.net v4 API：
file-urls/batch 申请上传链接 -> PUT 上传文件（自动提交任务）-> 轮询
extract-results/batch/{batch_id} -> 下载解析结果 zip（full.md + images/*）。
未配置 API Key 时使用 MockMinerUService，用 PyMuPDF 提取文本与内嵌图片。
"""

from __future__ import annotations

import asyncio
import io
import re
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("mineru")


class MinerURemoteError(RuntimeError):
    """MinerU 远程解析错误（携带可读信息）。"""


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

_MD_IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")


def _api_root(url: str) -> str:
    """把配置的 API URL 规整为 v4 根路径，兼容历史写法 …/v4/extract/task。"""
    root = url.rstrip("/")
    for suffix in ("/extract/task", "/extract-results", "/file-urls/batch"):
        if root.endswith(suffix):
            root = root[: -len(suffix)]
            break
    return root.rstrip("/")


def extract_md_images_from_zip(
    zip_bytes: bytes,
) -> tuple[str, list[ExtractedImage]]:
    """从 MinerU 结果 zip 中解析出 markdown 与图片。

    图片统一以「仅文件名」存入 images/（与仓库 images/ 存储布局一致），
    并据此改写 markdown 中的图片链接（去掉子目录前缀）。
    """
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = zf.namelist()
    md_name = _pick_markdown_name(zf, names)
    if not md_name:
        return "", []
    md = zf.read(md_name).decode("utf-8", errors="replace")

    entries = sorted(
        n
        for n in names
        if not n.endswith("/") and Path(n).suffix.lower() in IMAGE_EXTENSIONS
    )
    base_counts: dict[str, int] = {}
    for n in entries:
        base = Path(n).name
        base_counts[base] = base_counts.get(base, 0) + 1

    mapping: dict[str, str] = {}
    for n in entries:
        base = Path(n).name
        if base_counts[base] == 1:
            mapping[n] = base
        else:
            mapping[n] = n.replace("/", "_")

    images: list[ExtractedImage] = []
    seen: set[str] = set()
    for n in entries:
        stored = mapping[n]
        if stored in seen:
            continue
        seen.add(stored)
        images.append(
            ExtractedImage(
                name=stored,
                data=zf.read(n),
                ext=Path(n).suffix.lstrip(".").lower() or "png",
            )
        )

    by_stored = {mapping[n]: n for n in entries}

    def _rewrite_target(target: str) -> str:
        t = target.strip()
        path_part = t.split("?", 1)[0]
        if Path(path_part).suffix.lower() not in IMAGE_EXTENSIONS:
            return t
        if t in mapping:
            return "images/" + mapping[t]
        base = Path(path_part).name
        if base in by_stored:
            return "images/" + base
        return t

    md = _MD_IMAGE_LINK_RE.sub(
        lambda m: f"![{m.group(1)}]({_rewrite_target(m.group(2))})", md
    )
    return md, images


def _pick_markdown_name(zf: zipfile.ZipFile, names: list[str]) -> str | None:
    mds = [n for n in names if n.lower().endswith(".md")]
    if not mds:
        return None
    for cand in mds:
        if Path(cand).name.lower() == "full.md":
            return cand
    return max(mds, key=lambda n: zf.getinfo(n).file_size)


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
    """调用 MinerU 官方 v4 API（本地文件批量上传解析）。"""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model_version: str = "pipeline",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = _api_root(api_url)
        self.api_key = api_key
        self.model_version = model_version
        self._transport = transport

    async def parse_pdf(self, file_path: str | Path) -> ParseResult:
        path = Path(file_path)
        with open(path, "rb") as f:
            content = f.read()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(300.0, connect=30.0)
        async with httpx.AsyncClient(
            timeout=timeout, transport=self._transport
        ) as client:
            # 1) 申请上传链接
            resp = await client.post(
                f"{self.api_url}/file-urls/batch",
                headers=headers,
                json={
                    "files": [{"name": path.name, "data_id": uuid.uuid4().hex}],
                    "model_version": self.model_version,
                },
            )
            self._raise_readable(resp, "申请上传链接失败")
            body = resp.json()
            if body.get("code") != 0:
                raise MinerURemoteError(
                    f"申请上传链接失败: {body.get('msg') or resp.text[:300]}"
                )
            data = body.get("data") or {}
            batch_id = data.get("batch_id")
            upload_urls = data.get("file_urls") or []
            if not batch_id or not upload_urls:
                raise MinerURemoteError(
                    f"申请上传链接失败: 响应缺少 batch_id/file_urls: {resp.text[:300]}"
                )

            # 2) 上传文件，系统会自动提交解析任务
            up = await client.put(upload_urls[0], content=content)
            if up.status_code != 200:
                raise MinerURemoteError(f"文件上传失败: HTTP {up.status_code}")

            # 3) 轮询解析结果
            zip_url = await self._poll_result(client, headers, batch_id)

            # 4) 下载并解析结果 zip
            z = await client.get(zip_url)
            if z.status_code != 200:
                raise MinerURemoteError(f"下载解析结果失败: HTTP {z.status_code}")
            md, images = extract_md_images_from_zip(z.content)

        metadata = {
            "source": "remote",
            "model_version": self.model_version,
            "batch_id": batch_id,
            "result_zip_url": zip_url,
            "markdown_len": len(md),
            "image_count": len(images),
            "images": [i.name for i in images],
        }
        return ParseResult(
            markdown=md, images=images, metadata=metadata, source="remote"
        )

    @staticmethod
    def _raise_readable(resp: httpx.Response, context: str) -> None:
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise MinerURemoteError(
                f"{context}: HTTP {resp.status_code} {resp.text[:300]}"
            ) from e

    async def _poll_result(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        batch_id: str,
        *,
        interval: float = 4.0,
        timeout: float = 1800.0,
    ) -> str:
        url = f"{self.api_url}/extract-results/batch/{batch_id}"
        deadline = time.monotonic() + timeout
        while True:
            await asyncio.sleep(interval)
            if time.monotonic() > deadline:
                raise MinerURemoteError(
                    f"解析超时（超过 {int(timeout)}s），batch_id={batch_id}"
                )
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                continue
            body = resp.json()
            results = (body.get("data") or {}).get("extract_result") or []
            if not results:
                continue
            item = results[0]
            state = item.get("state")
            if state == "done":
                zip_url = item.get("full_zip_url")
                if not zip_url:
                    raise MinerURemoteError("解析完成但缺少 full_zip_url")
                return zip_url
            if state == "failed":
                raise MinerURemoteError(
                    f"解析失败: {item.get('err_msg') or '未知错误'}"
                )


def get_mineru_service() -> MinerUService:
    if settings.mineru_api_url and settings.mineru_api_key:
        return RemoteMinerUService(
            settings.mineru_api_url,
            settings.mineru_api_key,
            model_version=settings.mineru_model_version,
        )
    return MockMinerUService()
