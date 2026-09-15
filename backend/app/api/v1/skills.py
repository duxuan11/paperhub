"""Skill 管理 API：查看 / 新建 / 修改 / 删除自定义 Skill。

内置 Skill 是文件、只读；自定义 Skill 存在数据库，同名时覆盖内置，
删除自定义后内置恢复。Skill 正文仅由 Skill 系统维护，AI 分析只引用 Skill ID。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import require_auth
from app.schemas import SkillCreate, SkillDetail, SkillListOut, SkillUpdate
from app.services import skill_registry

router = APIRouter(
    prefix="/api/v1/skills", tags=["skills"], dependencies=[Depends(require_auth)]
)


@router.get("", response_model=SkillListOut)
async def list_skills(session: AsyncSession = Depends(get_session)):
    """当前可用 Skill（自定义优先，含来源标记与正文）。"""
    return SkillListOut(skills=await skill_registry.list_options(session))


@router.get("/{name}", response_model=SkillDetail)
async def get_skill(name: str, session: AsyncSession = Depends(get_session)):
    detail = await skill_registry.get_detail(session, name)
    if detail is None:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return detail


@router.post("", response_model=SkillDetail, status_code=201)
async def create_skill(
    req: SkillCreate, session: AsyncSession = Depends(get_session)
):
    """新建自定义 Skill；与内置同名即创建「覆盖内置」的副本。"""
    try:
        row = await skill_registry.create_skill(
            session,
            name=req.name,
            description=req.description,
            tools=req.tools,
            prompt=req.prompt,
        )
    except skill_registry.InvalidSkillName as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except skill_registry.SkillAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    detail = await skill_registry.get_detail(session, row.name)
    return detail


@router.put("/{name}", response_model=SkillDetail)
async def update_skill(
    name: str, req: SkillUpdate, session: AsyncSession = Depends(get_session)
):
    try:
        await skill_registry.update_skill(
            session,
            name,
            description=req.description,
            tools=req.tools,
            prompt=req.prompt,
        )
    except skill_registry.SkillNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    detail = await skill_registry.get_detail(session, name)
    return detail


@router.delete("/{name}", status_code=204)
async def delete_skill(name: str, session: AsyncSession = Depends(get_session)):
    try:
        await skill_registry.delete_skill(session, name)
    except skill_registry.SkillNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(status_code=204)
