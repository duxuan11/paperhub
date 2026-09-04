"""MinerU v4 API 适配器测试（httpx.MockTransport，不访问外网）。

验证 RemoteMinerUService 遵循 mineru.net v4 流程：
file-urls/batch 申请上传链接 -> PUT 文件 -> 轮询 extract-results/batch
-> 下载 zip（full.md + images/*）-> 解析出 markdown + 图片。
"""

import asyncio
import io
import zipfile

import httpx
import pytest

from pathlib import Path

from app.services.mineru import (
    ExtractedImage,
    MinerURemoteError,
    RemoteMinerUService,
    _api_root,
    extract_md_images_from_zip,
)


def run(coro):
    return asyncio.run(coro)


def build_zip(md: str, files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("full.md", md)
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


SAMPLE_ZIP = build_zip(
    "# T\n\n![fig](images/aaa.jpg)\n![fig2](images/sub/bbb.png)\n",
    {
        "images/aaa.jpg": b"jpeg-bytes",
        "images/sub/bbb.png": b"png-bytes",
    },
)

API_ROOT = "https://mineru.net/api/v4"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_PDF = str(REPO_ROOT / "demo" / "paper.pdf")


def make_transport(result_zip: bytes = SAMPLE_ZIP, poll_states=("running", "done")):
    calls = {"poll": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/file-urls/batch"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.example/presigned/up.pdf"],
                    },
                },
            )
        if request.method == "PUT":
            return httpx.Response(200)
        if path.endswith("/extract-results/batch/batch-1"):
            calls["poll"] += 1
            n = calls["poll"]
            state = poll_states[min(n - 1, len(poll_states) - 1)]
            body = {
                "code": 0,
                "data": {
                    "batch_id": "batch-1",
                    "extract_result": [{"file_name": "demo.pdf", "state": state}],
                },
            }
            if state == "done":
                body["data"]["extract_result"][0]["full_zip_url"] = (
                    "https://cdn.example/res.zip"
                )
            return httpx.Response(200, json=body)
        if path.endswith("/res.zip"):
            return httpx.Response(
                200,
                content=result_zip,
                headers={"Content-Type": "application/zip"},
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_api_root_strips_endpoint_suffixes():
    assert _api_root(f"{API_ROOT}/extract/task") == API_ROOT
    assert _api_root(f"{API_ROOT}/") == API_ROOT
    assert _api_root(API_ROOT) == API_ROOT


def test_extract_md_images_from_zip_rewrites_and_lists_images():
    md, images = extract_md_images_from_zip(SAMPLE_ZIP)
    assert md.startswith("# T")
    # 子目录图片被改写为仅文件名，保证与 images/ 存储布局一致
    assert "images/sub/bbb.png" not in md
    assert "images/bbb.png" in md
    assert "images/aaa.jpg" in md
    assert sorted(i.name for i in images) == ["aaa.jpg", "bbb.png"]
    assert {i.ext for i in images} == {"jpg", "png"}


def test_extract_md_images_from_zip_no_markdown_returns_empty():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("images/x.png", b"png")
    md, images = extract_md_images_from_zip(buf.getvalue())
    assert md == ""
    assert images == []


def test_remote_mineru_v4_parse_full_flow():
    svc = RemoteMinerUService(
        API_ROOT, "token", model_version="pipeline", transport=make_transport()
    )
    result = run(svc.parse_pdf(DEMO_PDF))
    assert result.source == "remote"
    assert result.markdown.startswith("# T")
    assert "images/aaa.jpg" in result.markdown
    assert isinstance(result.images, list)
    assert {i.name for i in result.images} >= {"aaa.jpg", "bbb.png"}


def test_remote_mineru_raise_when_apply_upload_url_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            return httpx.Response(
                200, json={"code": -10002, "msg": 'field "url" is not set'}
            )
        return httpx.Response(404)

    svc = RemoteMinerUService(API_ROOT, "token", transport=httpx.MockTransport(handler))
    with pytest.raises(MinerURemoteError, match="申请上传链接失败|url"):
        run(svc.parse_pdf(DEMO_PDF))


def test_remote_mineru_raise_on_state_failed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/file-urls/batch"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-fail",
                        "file_urls": ["https://upload.example/up.pdf"],
                    },
                },
            )
        if request.method == "PUT":
            return httpx.Response(200)
        if path := request.url.path.endswith("/extract-results/batch/batch-fail"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-fail",
                        "extract_result": [
                            {
                                "file_name": "demo.pdf",
                                "state": "failed",
                                "err_msg": "bad file",
                            }
                        ],
                    },
                },
            )
        return httpx.Response(404)

    svc = RemoteMinerUService(API_ROOT, "token", transport=httpx.MockTransport(handler))
    with pytest.raises(MinerURemoteError, match="解析失败|bad file"):
        run(svc.parse_pdf(DEMO_PDF))
