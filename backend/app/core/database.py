"""数据库引擎与会话管理（SQLAlchemy 2.x async）。"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """MVP：启动时自动建表（生产环境可替换为 Alembic 迁移）。

    ``create_all`` 不会给已存在的表补列，因此需要用向后兼容的
    ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` 兼顾旧库（新增字段全部 nullable）。
    新增表（如 ``wechat_article_themes``）由 ``create_all`` 直接创建，无需 ALTER。
    """
    from app import models  # noqa: F401  确保模型已注册

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            # Execute each migration separately to avoid asyncpg multi-statement limitation
            for migration_sql in _ARTICLE_MIGRATIONS:
                await conn.exec_driver_sql(migration_sql)
    await _seed_wechat_themes()


async def _seed_wechat_themes() -> None:
    """把内置公众号主题幂等写入 ``wechat_article_themes``（保留用户默认主题）。"""
    from app.services.wechat_theme import seed_builtin_themes

    async with async_session_factory() as session:
        await seed_builtin_themes(session)


# 新增且可为空的列：旧库升级后旧行自动为 NULL，不影响现有发布流程
# Each statement must be separate for asyncpg compatibility
_ARTICLE_MIGRATIONS = [
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS author VARCHAR(128);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS theme VARCHAR(64);",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS cover_image VARCHAR(1024);",
]


async def dispose_db() -> None:
    await engine.dispose()
