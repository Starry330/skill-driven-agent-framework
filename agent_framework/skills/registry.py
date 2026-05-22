"""skill 注册表。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from agent_framework.skills.loader import SkillLoader
from agent_framework.skills.models import SkillSpec


class SkillRegistry:
    """统一管理当前 agent 可见的 skill 集合。"""

    def __init__(self, loader: SkillLoader | None = None) -> None:
        self.loader = loader or SkillLoader()
        self._skills: Dict[str, SkillSpec] = {}

    def load_directory(self, path: str | Path) -> List[SkillSpec]:
        # 只认 SKILL.md，避免把 workspace 或其他 markdown 误当成 skill。
        loaded: List[SkillSpec] = []
        base = Path(path)
        for file_path in base.rglob("SKILL.md"):
            skill = self.loader.load(file_path)
            self._skills[skill.name] = skill
            loaded.append(skill)
        return loaded

    def register(self, skill: SkillSpec) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Optional[SkillSpec]:
        return self._skills.get(name)

    def all(self) -> List[SkillSpec]:
        return list(self._skills.values())

    def enabled(self) -> List[SkillSpec]:
        return [skill for skill in self._skills.values() if skill.enabled]

    def names(self) -> Iterable[str]:
        return self._skills.keys()
