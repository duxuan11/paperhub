"""PaperHub FastAPI 入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import dispose_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.minio import storage

log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    storage.ensure_bucket()
    log.info("PaperHub backend started")
    yield
    await dispose_db()


app = FastAPI(
    title="PaperHub API",
    version="0.1.0",
    description="论文 -> AI 分析 -> 微信公众号内容生成平台",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {"name": "PaperHub", "docs": "/docs", "health": "/api/v1/health"}
