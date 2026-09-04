"""Redis 连接（Arq 任务队列）。"""

from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings


def redis_settings() -> RedisSettings:
    # arq 接受 redis:// URL 解析
    return RedisSettings.from_dsn(settings.redis_url)


_pool = None


async def get_arq_pool():
    """复用连接池（worker 与 backend 入队共用）。"""
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
