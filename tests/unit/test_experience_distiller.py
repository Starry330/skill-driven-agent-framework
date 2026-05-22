"""test_experience_distiller.py — 经验提炼器单元测试。"""

import unittest
from unittest.mock import MagicMock

from agent_framework.memory.models import (
    EpisodicExperience,
    ProceduralExperience,
    ReflectionResult,
    UserPreference,
)
from agent_framework.memory.reflection.distiller import ExperienceDistiller


class ExperienceDistillerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_store = MagicMock()
        self.mock_store.search.return_value = []
        self.distiller = ExperienceDistiller(self.mock_store)

    def test_distill_procedure(self) -> None:
        """测试程序性经验提炼。"""
        reflection = ReflectionResult(
            outcome="success",
            procedures=[
                ProceduralExperience(
                    task_pattern="创建Agent",
                    steps=["步骤1", "步骤2"],
                    content="完整的程序性经验描述",
                    confidence=0.7,
                )
            ],
        )

        records = self.distiller.distill(reflection)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].namespace, "procedures")
        self.assertEqual(records[0].experience_type, "procedure")
        self.assertIn("创建Agent", records[0].content)

    def test_distill_episode(self) -> None:
        """测试情景记忆提炼。"""
        reflection = ReflectionResult(
            outcome="success",
            episodes=[
                EpisodicExperience(
                    context_summary="用户要求创建研究Agent",
                    outcome="success",
                    key_factors=["需求明确"],
                    content="成功案例描述",
                    confidence=0.8,
                )
            ],
        )

        records = self.distiller.distill(reflection)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].namespace, "episodes")
        self.assertEqual(records[0].experience_type, "episode")
        self.assertIn("成功", records[0].content)

    def test_distill_preference(self) -> None:
        """测试用户偏好提炼。"""
        reflection = ReflectionResult(
            outcome="success",
            preferences=[
                UserPreference(
                    category="language",
                    content="用户偏好中文交流",
                    evidence=["用户全程使用中文"],
                    confidence=0.9,
                )
            ],
        )

        records = self.distiller.distill(reflection)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].namespace, "user_preferences")
        self.assertEqual(records[0].experience_type, "preference")
        self.assertIn("中文", records[0].content)

    def test_distill_lessons(self) -> None:
        """测试经验教训提炼。"""
        reflection = ReflectionResult(
            outcome="success",
            lessons=["需求收集阶段要充分", "要验证工具可用性"],
        )

        records = self.distiller.distill(reflection)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].namespace, "semantic")
        self.assertEqual(records[0].experience_type, "lesson")

    def test_distill_empty_content(self) -> None:
        """测试空内容不提炼。"""
        reflection = ReflectionResult(
            outcome="success",
            procedures=[
                ProceduralExperience(
                    task_pattern="test",
                    steps=[],
                    content="",  # 空内容
                    confidence=0.5,
                )
            ],
        )

        records = self.distiller.distill(reflection)
        self.assertEqual(len(records), 0)

    def test_distill_with_existing_similar(self) -> None:
        """测试去重逻辑。"""
        # 模拟已存在相似记忆
        from agent_framework.memory.models import MemoryRecord

        existing = MemoryRecord(
            namespace="procedures",
            key="existing",
            content="任务模式: 创建Agent\n步骤:\n1. 步骤1\n2. 步骤2\n\n描述: 完整的程序性经验描述",
            experience_type="procedure",
            confidence=0.5,
        )
        self.mock_store.search.return_value = [existing]

        reflection = ReflectionResult(
            outcome="success",
            procedures=[
                ProceduralExperience(
                    task_pattern="创建Agent",
                    steps=["步骤1", "步骤2"],
                    content="完整的程序性经验描述",
                    confidence=0.7,
                )
            ],
        )

        records = self.distiller.distill(reflection)
        # 应该不创建新记录，而是更新现有记录的置信度
        self.assertEqual(len(records), 0)
        self.mock_store.store.assert_called_once()


if __name__ == "__main__":
    unittest.main()
