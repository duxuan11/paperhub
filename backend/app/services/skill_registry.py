"""自定义 Skill 的加载与 CRUD。

自定义 Skill 持久化在 ``custom_skills`` 表，与内置文件 Skill 合并后使用：
- :func:`load_registry` 在异步上下文把 DB 自定义 Skill 读成 ``{name: Skill}``，
  传给 :func:`app.services.skill.load_skill` / ``list_skills``；
- ``name`` 与内置同名即覆盖内置；删除自定义后内置恢复。
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app import models, repositories
from app.services.skill import Skill, list_skill_options

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class SkillStoreError(Exception):
    """自定义 Skill 操作错误基类。"""


class InvalidSkillName(SkillStoreError):
    pass


class SkillAlreadyExists(SkillStoreError):
    pass


class SkillNotFound(SkillStoreError):
    pass


def validate_name(name: str) -> str:
    name = (name or "").strip()
    if not NAME_PATTERN.match(name):
        raise InvalidSkillName(
            "Skill 名称只能包含小写字母、数字与连字符，且以字母或数字开头（不超过 64 字符）"
        )
    return name


async def load_registry(session: AsyncSession) -> dict[str, Skill]:
    """把数据库自定义 Skill 读成 ``{name: Skill}``（source=custom）。"""
    rows = await repositories.list_custom_skills(session)
    return {
        row.name: Skill(
            name=row.name,
            description=row.description or "",
            prompt=row.prompt or "",
            tools=list(row.tools or []),
            source="custom",
        )
        for row in rows
    }


async def list_options(session: AsyncSession) -> list[dict]:
    """可用 Skill 列表（含正文与来源标记）。"""
    return list_skill_options(await load_registry(session))


async def get_detail(session: AsyncSession, name: str) -> dict | None:
    for item in await list_options(session):
        if item["name"] == name:
            return item
    return None


async def create_skill(
    session: AsyncSession,
    *,
    name: str,
    description: str = "",
    tools: list[str] | None = None,
    prompt: str = "",
) -> models.CustomSkill:
    name = validate_name(name)
    if await repositories.get_custom_skill(session, name) is not None:
        raise SkillAlreadyExists(f"自定义 Skill 已存在：{name}")
    row = models.CustomSkill(
        name=name,
        description=(description or "").strip(),
        tools=list(tools or []),
        prompt=prompt or "",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def update_skill(
    session: AsyncSession,
    name: str,
    *,
    description: str | None = None,
    tools: list[str] | None = None,
    prompt: str | None = None,
) -> models.CustomSkill:
    row = await repositories.get_custom_skill(session, name)
    if row is None:
        raise SkillNotFound(f"自定义 Skill 不存在：{name}")
    if description is not None:
        row.description = description.strip()
    if tools is not None:
        row.tools = list(tools)
    if prompt is not None:
        row.prompt = prompt
    await session.commit()
    await session.refresh(row)
    return row


async def delete_skill(session: AsyncSession, name: str) -> None:
    row = await repositories.get_custom_skill(session, name)
    if row is None:
        raise SkillNotFound(f"自定义 Skill 不存在：{name}")
    await session.delete(row)
    await session.commit()
