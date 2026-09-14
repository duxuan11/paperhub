"""微信公众号推文主题（Theme）服务。

职责：
- 提供主题的 CRUD（持久化在 ``wechat_article_themes``）；
- 启动时把 :data:`publishers.wechat.themes.BUILTIN_THEMES` 幂等写入数据库；
- 把数据库中的**设计变量**编译为渲染器使用的 :class:`WeChatTheme`，供发布链路调用。

内置主题 ``is_builtin=True``：可查看 / 预览 / 设为默认 / 复制，但不能直接编辑或删除，
需要修改时先「复制为自定义主题」。
"""

from __future__ import annotations

import sys
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories
from app.core.logging import get_logger
from app.schemas import WechatThemeOut

# 确保仓库根目录在 sys.path，使 publishers 包可被导入（原生与 Docker 通用）
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from publishers.wechat.theme_config import compile_styles, merge_config  # noqa: E402
from publishers.wechat.themes import (  # noqa: E402
    BUILTIN_THEMES,
    DEFAULT_THEME_ID,
    WeChatTheme,
    get_theme,
)

log = get_logger("wechat_theme")


class WeChatThemeError(Exception):
    """主题操作的基类错误。"""


class WeChatThemeNotFound(WeChatThemeError):
    def __init__(self, theme_id: str) -> None:
        super().__init__(f"主题不存在: {theme_id}")
        self.theme_id = theme_id


class BuiltinThemeImmutable(WeChatThemeError):
    def __init__(self, theme_id: str) -> None:
        super().__init__(f"内置主题不可编辑或删除，请先复制为自定义主题: {theme_id}")
        self.theme_id = theme_id


def to_out(row: models.WeChatArticleTheme) -> WechatThemeOut:
    """数据库行 -> API 响应（含设计变量与编译后的 styles）。"""
    config = merge_config(row.config or {})
    return WechatThemeOut(
        id=row.id,
        name=row.name,
        description=row.description or "",
        config=config,
        styles=compile_styles(config),
        is_builtin=bool(row.is_builtin),
        is_default=bool(row.is_default),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_themes(session: AsyncSession) -> Sequence[models.WeChatArticleTheme]:
    return await repositories.list_wechat_themes(session)


async def get_theme_or_none(
    session: AsyncSession, theme_id: str | None
) -> models.WeChatArticleTheme | None:
    if not theme_id:
        return None
    return await repositories.get_wechat_theme(session, theme_id)


async def _clear_default(session: AsyncSession, *, keep_id: str | None = None) -> None:
    for row in await repositories.list_wechat_themes(session):
        if row.id != keep_id and row.is_default:
            row.is_default = False


async def create_theme(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    config: dict | None = None,
    is_default: bool = False,
) -> models.WeChatArticleTheme:
    row = models.WeChatArticleTheme(
        id=uuid.uuid4().hex,
        name=name.strip(),
        description=description,
        config=merge_config(config or {}),
        is_builtin=False,
        is_default=False,
    )
    session.add(row)
    if is_default:
        await _clear_default(session, keep_id=row.id)
        row.is_default = True
    await session.commit()
    await session.refresh(row)
    return row


async def update_theme(
    session: AsyncSession,
    theme_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    config: dict | None = None,
) -> models.WeChatArticleTheme:
    row = await get_theme_or_none(session, theme_id)
    if row is None:
        raise WeChatThemeNotFound(theme_id)
    if row.is_builtin:
        raise BuiltinThemeImmutable(theme_id)
    if name is not None:
        row.name = name.strip()
    if description is not None:
        row.description = description
    if config is not None:
        row.config = merge_config(config)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_theme(session: AsyncSession, theme_id: str) -> None:
    row = await get_theme_or_none(session, theme_id)
    if row is None:
        raise WeChatThemeNotFound(theme_id)
    if row.is_builtin:
        raise BuiltinThemeImmutable(theme_id)
    was_default = bool(row.is_default)
    await session.delete(row)
    if was_default:
        fallback = await repositories.get_wechat_theme(session, DEFAULT_THEME_ID)
        if fallback is not None:
            fallback.is_default = True
    await session.commit()


async def duplicate_theme(
    session: AsyncSession,
    theme_id: str,
    *,
    name: str | None = None,
) -> models.WeChatArticleTheme:
    src = await get_theme_or_none(session, theme_id)
    if src is None:
        raise WeChatThemeNotFound(theme_id)
    row = models.WeChatArticleTheme(
        id=uuid.uuid4().hex,
        name=(name or f"{src.name}（副本）").strip(),
        description=src.description,
        config=deepcopy(src.config or {}),
        is_builtin=False,
        is_default=False,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def set_default_theme(
    session: AsyncSession, theme_id: str
) -> models.WeChatArticleTheme:
    row = await get_theme_or_none(session, theme_id)
    if row is None:
        raise WeChatThemeNotFound(theme_id)
    for theme in await repositories.list_wechat_themes(session):
        theme.is_default = theme.id == theme_id
    await session.commit()
    await session.refresh(row)
    return row


async def resolve_theme(session: AsyncSession, theme_id: str | None) -> WeChatTheme:
    """按 id 解析出可渲染的主题：优先数据库，失败/缺失回退内置注册表。

    发布链路调用本函数，因此用户自定义主题无需重启 Worker 即可生效。
    """
    try:
        row = await get_theme_or_none(session, theme_id)
    except Exception as e:  # noqa: BLE001 —— 主题读取失败不应阻断发布
        log.warning("读取主题失败，回退内置主题: %s", e)
        row = None
    if row is not None and row.config:
        config = merge_config(row.config)
        return WeChatTheme(
            id=row.id,
            name=row.name,
            description=row.description or "",
            styles=compile_styles(config),
            config=config,
            is_builtin=bool(row.is_builtin),
        )
    return get_theme(theme_id)


async def seed_builtin_themes(session: AsyncSession) -> None:
    """启动时把内置主题幂等写入数据库（保留用户设置的默认主题）。

    API 与 Arq Worker 会同时调用 ``init_db``，因此这里对并发写入做重试：
    若另—个进程先插入了相同的内置主题（主键冲突），回滚后重读并继续。
    """
    for _attempt in range(3):
        existing = {
            row.id: row for row in await repositories.list_wechat_themes(session)
        }
        for theme in BUILTIN_THEMES:
            row = existing.get(theme.id)
            if row is None:
                row = models.WeChatArticleTheme(
                    id=theme.id,
                    name=theme.name,
                    description=theme.description,
                    config=theme.config,
                    is_builtin=True,
                    is_default=False,
                )
                session.add(row)
                existing[theme.id] = row
            else:
                row.name = theme.name
                row.description = theme.description
                row.config = theme.config
                row.is_builtin = True
        if not any(row.is_default for row in existing.values()):
            fallback = existing.get(DEFAULT_THEME_ID)
            if fallback is not None:
                fallback.is_default = True
        try:
            await session.commit()
            return
        except IntegrityError:
            # 另一个进程已并发写入内置主题，重试即可
            await session.rollback()
            continue
    log.warning("内置主题并发写入重试失败，跳过本次 seed（主题已由其他进程写入）")
