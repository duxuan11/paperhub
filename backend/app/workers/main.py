"""Arq Worker 入口。"""

from __future__ import annotations

import asyncio

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.database import dispose_db, init_db
from app.core.logging import get_logger, setup_logging
from app.core.minio import storage
from app.workers.tasks import (
    analyze_paper,
    detect_figures,
    generate_wechat_article,
    parse_paper,
    publish_wechat_article,
)

log = get_logger("worker")


async def startup(ctx: dict) -> None:
    setup_logging()
    await init_db()
    storage.ensure_bucket()
    log.info("worker startup ok")


async def shutdown(ctx: dict) -> None:
    await dispose_db()


class WorkerSettings:
    functions = [
        parse_paper,
        detect_figures,
        analyze_paper,
        generate_wechat_article,
        publish_wechat_article,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 3
    retry_jobs = True
    keep_result = 60
