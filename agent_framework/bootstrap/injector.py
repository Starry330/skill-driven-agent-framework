"""把 bootstrap、skills、memory 命中结果组合成最终 prompt section。"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from agent_framework.bootstrap.models import BootstrapSection, BootstrapSnapshot
from agent_framework.skills.models import SkillSpec


class BootstrapInjector:
    """负责 prompt section 级别的拼装。

    它不关心文档从哪里来，只关心哪些内容应该进入系统提示词，以及以什么顺序进入。
    """

    def build_prompt_sections(
        self,
        snapshot: BootstrapSnapshot,
        active_skills: Sequence[SkillSpec],
        memory_hits: Sequence[str],
        summary: str,
        mode: str = "main",
        task_brief: str | None = None,
    ) -> List[BootstrapSection]:
        # 先使用 workspace 静态文档，再叠加 task、skills、memory、summary 这些运行时层。
        sections = snapshot.build_sections(mode)
        if task_brief:
            sections.append(
                BootstrapSection(
                    title="TASK_BRIEF",
                    content=task_brief.strip(),
                    source="runtime",
                    mode="system",
                )
            )

        for skill in active_skills:
            sections.append(
                BootstrapSection(
                    title=f"SKILL::{skill.name}",
                    content=skill.render_protocol_prompt(),
                    source=str(skill.path),
                    mode="skill",
                )
            )

        if memory_hits:
            sections.append(
                BootstrapSection(
                    title="MEMORY_HITS",
                    content="\n".join(memory_hits),
                    source="memory",
                    mode="memory",
                )
            )

        if summary:
            sections.append(
                BootstrapSection(
                    title="SESSION_SUMMARY",
                    content=summary.strip(),
                    source="session",
                    mode="summary",
                )
            )
        return sections

    def render_system_prompt(self, sections: Iterable[BootstrapSection]) -> str:
        # 用统一 section 头保留来源，便于模型区分“规则 / 技能 / 记忆 / 摘要”。
        rendered: List[str] = []
        for section in sections:
            rendered.append(f"[{section.title} | source={section.source} | mode={section.mode}]\n{section.content}")
        return "\n\n".join(rendered)
