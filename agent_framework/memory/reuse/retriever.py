"""经验复用器：检索相关经验并格式化为可操作指导。"""

from __future__ import annotations

import logging
from typing import Dict, List, Sequence

from agent_framework.memory.long_term_memory.base import LongTermMemoryStore
from agent_framework.memory.models import MemoryRecord
from agent_framework.skills.models import SkillSpec

logger = logging.getLogger(__name__)


class ExperienceReuser:
    """经验复用器：检索相关经验并格式化为可操作指导。"""

    def __init__(self, long_term_store: LongTermMemoryStore) -> None:
        self.long_term_store = long_term_store

    def retrieve_experiences(
        self,
        query: str,
        namespaces: List[str],
        top_k: int = 5,
    ) -> List[MemoryRecord]:
        """检索相关经验。"""
        try:
            # 使用评分检索
            if hasattr(self.long_term_store, "search_with_score"):
                return self.long_term_store.search_with_score(query, namespaces, top_k)
            else:
                return self.long_term_store.search(query, namespaces)[:top_k]
        except Exception:
            logger.debug("检索经验失败")
            return []

    def format_experiences_for_prompt(self, experiences: List[MemoryRecord]) -> str:
        """将经验格式化为prompt注入格式。"""
        if not experiences:
            return ""

        sections = []

        # 按经验类型分组
        procedures = [e for e in experiences if e.experience_type == "procedure"]
        episodes = [e for e in experiences if e.experience_type == "episode"]
        preferences = [e for e in experiences if e.experience_type == "preference"]
        lessons = [e for e in experiences if e.experience_type == "lesson"]

        if procedures:
            sections.append("## 相关程序性经验")
            for i, proc in enumerate(procedures[:3], 1):
                sections.append(f"{i}. {proc.content[:500]}")

        if episodes:
            sections.append("## 相关情景记忆")
            for i, ep in enumerate(episodes[:3], 1):
                sections.append(f"{i}. {ep.content[:500]}")

        if preferences:
            sections.append("## 用户偏好")
            for pref in preferences[:2]:
                sections.append(f"- {pref.content[:200]}")

        if lessons:
            sections.append("## 经验教训")
            for lesson in lessons[:2]:
                sections.append(f"- {lesson.content[:200]}")

        return "\n\n".join(sections)

    def boost_skill_routing(
        self,
        skills: Sequence[SkillSpec],
        user_input: str,
        boost_factor: float = 2.0,
    ) -> List[SkillSpec]:
        """基于历史经验提升技能路由分数。"""
        if not skills:
            return list(skills)

        # 检索与技能相关的情景记忆
        episodic_experiences = self.retrieve_experiences(
            user_input,
            ["episodes"],
            top_k=10,
        )

        # 构建技能名称到正面经验的映射
        skill_boosts: Dict[str, float] = {}
        for exp in episodic_experiences:
            if exp.metadata.get("outcome") == "success":
                # 从经验内容中提取可能的技能名称
                content_lower = exp.content.lower()
                for skill in skills:
                    if skill.name.lower() in content_lower:
                        skill_boosts[skill.name] = skill_boosts.get(skill.name, 0) + boost_factor

        # 应用分数提升
        boosted_skills = []
        for skill in skills:
            boosted = SkillSpec(
                name=skill.name,
                description=skill.description,
                body=skill.body,
                path=skill.path,
                triggers=skill.triggers,
                required_tools=skill.required_tools,
                permissions=skill.permissions,
                input_schema=skill.input_schema,
                output_schema=skill.output_schema,
                decision_logic=skill.decision_logic,
                constraints=skill.constraints,
                failure_modes=skill.failure_modes,
                fallback_strategy=skill.fallback_strategy,
                tool_policy=skill.tool_policy,
                dependencies=skill.dependencies,
                availability_checks=skill.availability_checks,
                subagent_allowed=skill.subagent_allowed,
                enabled=skill.enabled,
                metadata=skill.metadata,
                routing_score=skill.routing_score + skill_boosts.get(skill.name, 0),
                available=skill.available,
                unavailable_reason=skill.unavailable_reason,
            )
            boosted_skills.append(boosted)

        return boosted_skills

    def update_usage_stats(self, experiences: List[MemoryRecord]) -> None:
        """更新经验的使用统计。"""
        for exp in experiences:
            try:
                if hasattr(self.long_term_store, "update_memory_stats"):
                    self.long_term_store.update_memory_stats(exp.namespace, exp.key)
            except Exception:
                logger.debug("更新使用统计失败")
