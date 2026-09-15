"""Skill 系统：加载 skills/*/SKILL.md，解析 YAML frontmatter + 模板。

内置 Skill 是仓库内的文件；用户自定义 Skill 存在数据库（见
:mod:`app.services.skill_registry`），加载时以「自定义优先」的方式叠加：

- 同名时自定义 Skill 覆盖内置（即「编辑内置 Skill」的落地方式）；
- 调用方在异步上下文里先从数据库加载 registry，再传给 ``load_skill`` /
  ``list_skills``，因此 API 与 Worker 两个进程都能看到最新自定义 Skill。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("skill")


@dataclass
class Skill:
    name: str
    description: str = ""
    prompt: str = ""
    tools: list[str] = field(default_factory=list)
    path: Path | None = None
    source: str = "builtin"  # builtin | custom

    def render(self, **variables: str) -> str:
        prompt = self.prompt
        for k, v in variables.items():
            prompt = prompt.replace("{" + k + "}", v or "")
        return prompt


def _skill_bases() -> list[Path]:
    return [
        settings.skills_path,
        Path(__file__).resolve().parents[3] / "skills",
    ]


def _builtin_skill_dirs() -> dict[str, Path]:
    """内置 Skill 目录映射（name -> dir），后者不覆盖前者。"""
    out: dict[str, Path] = {}
    for base in _skill_bases():
        if not base.exists():
            continue
        for d in base.iterdir():
            if (d / "SKILL.md").exists() and d.name not in out:
                out[d.name] = d
    return out


def builtin_skill_names() -> list[str]:
    return list(_builtin_skill_dirs().keys())


def is_builtin_skill(name: str) -> bool:
    return name in _builtin_skill_dirs()


def _load_builtin_skill(name: str) -> Skill | None:
    base = settings.skills_path / name
    if not base.exists():
        base = Path(__file__).resolve().parents[3] / "skills" / name
    skill_file = base / "SKILL.md"
    if not skill_file.exists():
        return None
    text = skill_file.read_text(encoding="utf-8")
    frontmatter: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError as e:
                log.warning("Skill frontmatter 解析失败 %s: %s", name, e)
            body = parts[2]
    return Skill(
        name=name,
        description=frontmatter.get("description", ""),
        prompt=body.strip(),
        tools=frontmatter.get("tools", []),
        path=skill_file,
        source="builtin",
    )


def load_skill(
    name: str, registry: Mapping[str, Skill] | None = None
) -> Skill | None:
    """加载 Skill；``registry``（自定义 Skill）中同名项优先于内置文件。"""
    if registry and name in registry:
        return registry[name]
    return _load_builtin_skill(name)


def list_skills(registry: Mapping[str, Skill] | None = None) -> list[dict]:
    """列出可用 Skill（自定义在前，同名内置被隐藏）。"""
    custom = registry or {}
    out: list[dict] = [
        {
            "name": name,
            "description": skill.description,
            "tools": list(skill.tools or []),
            "source": "custom",
            "is_builtin": False,
        }
        for name, skill in custom.items()
    ]
    for name in _builtin_skill_dirs():
        if name in custom:
            continue
        s = _load_builtin_skill(name)
        if s:
            out.append(
                {
                    "name": s.name,
                    "description": s.description,
                    "tools": list(s.tools or []),
                    "source": "builtin",
                    "is_builtin": True,
                }
            )
    return out


def list_skill_options(registry: Mapping[str, Skill] | None = None) -> list[dict]:
    """列表 + 正文，供「AI 分析」Skill 选择器与设置页编辑器使用。"""
    builtin_names = set(_builtin_skill_dirs())
    out: list[dict] = []
    for meta in list_skills(registry):
        name = meta["name"]
        skill = load_skill(name, registry=registry)
        if not skill:
            continue
        out.append(
            {
                "name": name,
                "description": skill.description,
                "tools": list(skill.tools or []),
                "prompt": skill.prompt,
                "source": meta["source"],
                "is_builtin": meta["is_builtin"],
                "overrides_builtin": meta["source"] == "custom" and name in builtin_names,
            }
        )
    return out
