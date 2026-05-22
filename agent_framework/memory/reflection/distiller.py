"""经验提炼器：将反思结果转换为可存储的记忆记录。"""

from __future__ import annotations

import json
import logging
from typing import List

from agent_framework.memory.models import (
    EpisodicExperience,
    MemoryRecord,
    ProceduralExperience,
    ReflectionResult,
    UserPreference,
)

logger = logging.getLogger(__name__)


class ExperienceDistiller:
    """将反思结果转换为可存储的记忆记录。"""

    def __init__(self, long_term_store: object) -> None:
        self.long_term_store = long_term_store

    def distill(self, reflection: ReflectionResult) -> List[MemoryRecord]:
        """将反思结果提炼为记忆记录。"""
        records = []

        # 提炼程序性经验
        for procedure in reflection.procedures:
            record = self._distill_procedure(procedure)
            if record:
                records.append(record)

        # 提炼情景记忆
        for episode in reflection.episodes:
            record = self._distill_episode(episode)
            if record:
                records.append(record)

        # 提炼用户偏好
        for preference in reflection.preferences:
            record = self._distill_preference(preference)
            if record:
                records.append(record)

        # 提炼经验教训
        for lesson in reflection.lessons:
            if lesson.strip():
                record = MemoryRecord(
                    namespace="semantic",
                    key="",
                    content=f"经验教训: {lesson}",
                    metadata={
                        "source": "reflection",
                        "type": "lesson",
                        "outcome": reflection.outcome,
                    },
                    experience_type="lesson",
                    confidence=0.6,
                )
                records.append(record)

        return records

    def _distill_procedure(self, procedure: ProceduralExperience) -> MemoryRecord | None:
        """提炼程序性经验。"""
        if not procedure.content.strip():
            return None

        # 检查去重
        existing = self._find_similar("procedures", procedure.content)
        if existing:
            self._update_confidence(existing, procedure.confidence)
            return None

        content = f"任务模式: {procedure.task_pattern}\n步骤:\n"
        for i, step in enumerate(procedure.steps, 1):
            content += f"{i}. {step}\n"
        content += f"\n描述: {procedure.content}"

        return MemoryRecord(
            namespace="procedures",
            key="",
            content=content,
            metadata={
                "source": "reflection",
                "task_pattern": procedure.task_pattern,
                "steps": procedure.steps,
            },
            experience_type="procedure",
            confidence=procedure.confidence,
            task_pattern=procedure.task_pattern,
        )

    def _distill_episode(self, episode: EpisodicExperience) -> MemoryRecord | None:
        """提炼情景记忆。"""
        if not episode.content.strip():
            return None

        # 检查去重
        existing = self._find_similar("episodes", episode.content)
        if existing:
            self._update_confidence(existing, episode.confidence)
            return None

        content = f"上下文: {episode.context_summary}\n"
        content += f"结果: {episode.outcome}\n"
        content += f"关键因素: {', '.join(episode.key_factors)}\n"
        content += f"\n描述: {episode.content}"

        return MemoryRecord(
            namespace="episodes",
            key="",
            content=content,
            metadata={
                "source": "reflection",
                "context_summary": episode.context_summary,
                "outcome": episode.outcome,
                "key_factors": episode.key_factors,
            },
            experience_type="episode",
            confidence=episode.confidence,
        )

    def _distill_preference(self, preference: UserPreference) -> MemoryRecord | None:
        """提炼用户偏好。"""
        if not preference.content.strip():
            return None

        # 检查去重
        existing = self._find_similar("user_preferences", preference.content)
        if existing:
            self._update_confidence(existing, preference.confidence)
            return None

        content = f"类别: {preference.category}\n"
        content += f"描述: {preference.content}\n"
        content += f"证据: {', '.join(preference.evidence)}"

        return MemoryRecord(
            namespace="user_preferences",
            key="",
            content=content,
            metadata={
                "source": "reflection",
                "category": preference.category,
                "evidence": preference.evidence,
            },
            experience_type="preference",
            confidence=preference.confidence,
        )

    def _find_similar(self, namespace: str, content: str) -> MemoryRecord | None:
        """查找相似的记忆记录。"""
        try:
            # 简单的关键词匹配去重
            keywords = set(content.lower().split()[:10])
            records = self.long_term_store.search(content[:50], [namespace])

            for record in records:
                record_keywords = set(record.content.lower().split()[:10])
                overlap = len(keywords & record_keywords)
                if overlap >= len(keywords) * 0.5:
                    return record
        except Exception:
            logger.debug("查找相似记忆失败")
        return None

    def _update_confidence(self, record: MemoryRecord, new_confidence: float) -> None:
        """更新记忆的置信度。"""
        try:
            # 简单的置信度更新：取平均值
            avg_confidence = (record.confidence + new_confidence) / 2
            record.confidence = min(1.0, max(0.1, avg_confidence))
            self.long_term_store.store(record)
        except Exception:
            logger.debug("更新置信度失败")
