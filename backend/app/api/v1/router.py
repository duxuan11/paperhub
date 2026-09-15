"""API v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import (
    analysis,
    articles,
    chat,
    files,
    jobs,
    misc,
    papers,
    skills,
    wechat,
    wechat_themes,
)

api_router = APIRouter()
api_router.include_router(papers.router)
api_router.include_router(analysis.router)
api_router.include_router(skills.router)
api_router.include_router(jobs.router)
api_router.include_router(articles.router)
api_router.include_router(wechat.router)
api_router.include_router(wechat_themes.router)
api_router.include_router(files.router)
api_router.include_router(chat.router)
api_router.include_router(misc.router)
