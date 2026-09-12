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
    """
    from app import models  # noqa: F401  确保模型已注册

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if conn.dialect.name == "postgresql":
            await conn.exec_driver_sql(_ARTICLE_MIGRATIONS)


# 新增且可为空的列：旧库升级后旧行自动为 NULL，不影响现有发布流程
_ARTICLE_MIGRATIONS = """
ALTER TABLE articles ADD COLUMN IF NOT EXISTS author VARCHAR(128);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS theme VARCHAR(64);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS cover_image VARCHAR(1024);
"""


async def dispose_db() -> None:
    await engine.dispose()
