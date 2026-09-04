"""Skill 系统：加载 skills/*/SKILL.md，解析 YAML frontmatter + 模板。"""

from __future__ import annotations

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

    def render(self, **variables: str) -> str:
        prompt = self.prompt
        for k, v in variables.items():
            prompt = prompt.replace("{" + k + "}", v or "")
        return prompt


def load_skill(name: str) -> Skill | None:
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
    )


def list_skills() -> list[dict]:
    out: list[dict] = []
    for base in (settings.skills_path, Path(__file__).resolve().parents[3] / "skills"):
        if not base.exists():
            continue
        for d in base.iterdir():
            if (d / "SKILL.md").exists():
                s = load_skill(d.name)
                if s:
                    out.append(
                        {"name": s.name, "description": s.description, "tools": s.tools}
                    )
    seen: set[str] = set()
    dedup = []
    for s in out:
        if s["name"] not in seen:
            seen.add(s["name"])
            dedup.append(s)
    return dedup
