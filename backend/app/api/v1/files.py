"""通用文件/图片读取（从 MinIO 代理）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.minio import storage
from app.core.security import require_auth

router = APIRouter(
    prefix="/api/v1/files", tags=["files"], dependencies=[Depends(require_auth)]
)


@router.get("/{key:path}")
async def get_file(key: str):
    data = storage.get_bytes(key)
    if data is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    content_type = "image/png"
    if key.endswith(".md"):
        content_type = "text/markdown"
    elif key.endswith(".json"):
        content_type = "application/json"
    elif key.endswith(".pdf"):
        content_type = "application/pdf"
    elif key.endswith(".jpg") or key.endswith(".jpeg"):
        content_type = "image/jpeg"
    return Response(content=data, media_type=content_type)
