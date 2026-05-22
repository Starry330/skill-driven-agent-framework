"""test_experience_retriever.py — 经验复用器单元测试。"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from agent_framework.memory.models import MemoryRecord
from agent_framework.memory.reuse.retriever import ExperienceReuser
from agent_framework.skills.models import SkillSpec


class ExperienceReuserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_store = MagicMock()
        self.reuser = ExperienceReuser(self.mock_store)

    def test_retrieve_experiences(self) -> None:
        """测试经验检索。"""
        # 模拟存储返回结果
        mock_records = [
            MemoryRecord(
                namespace="procedures",
                key="test1",
                content="创建Agent的步骤",
                experience_type="procedure",
            )
        ]
        self.mock_store.search_with_score.return_value = mock_records

        results = self.reuser.retrieve_experiences("创建Agent", ["procedures"])
        self.assertEqual(len(results), 1)
        self.mock_store.search_with_score.assert_called_once()

    def test_format_experiences_for_prompt(self) -> None:
        """测试经验格式化。"""
        experiences = [
            MemoryRecord(
                namespace="procedures",
                key="test1",
                content="创建Agent的步骤：1.收集需求 2.设计蓝图",
                experience_type="procedure",
            ),
            MemoryRecord(
                namespace="episodes",
                key="test2",
                content="成功创建研究Agent的案例",
                experience_type="episode",
            ),
        ]

        formatted = self.reuser.format_experiences_for_prompt(experiences)
        self.assertIn("程序性经验", formatted)
        self.assertIn("情景记忆", formatted)
        self.assertIn("创建Agent的步骤", formatted)

    def test_format_empty_experiences(self) -> None:
        """测试空经验列表格式化。"""
        formatted = self.reuser.format_experiences_for_prompt([])
        self.assertEqual(formatted, "")

    def test_boost_skill_routing(self) -> None:
        """测试技能路由分数提升。"""
        # 模拟存储返回成功经验
        mock_records = [
            MemoryRecord(
                namespace="episodes",
                key="test1",
                content="使用web-search技能成功搜索到信息",
                experience_type="episode",
                metadata={"outcome": "success"},
            )
        ]
        self.mock_store.search_with_score.return_value = mock_records

        # 创建测试技能
        skills = [
            SkillSpec(
                name="web-search",
                description="Web搜索技能",
                body="搜索内容",
                path=Path("test"),
            )
        ]

        boosted = self.reuser.boost_skill_routing(skills, "搜索信息")
        self.assertEqual(len(boosted), 1)
        # 应该有分数提升
        self.assertGreater(boosted[0].routing_score, 0)

    def test_boost_skill_routing_no_match(self) -> None:
        """测试无匹配经验时的路由。"""
        self.mock_store.search_with_score.return_value = []

        skills = [
            SkillSpec(
                name="web-search",
                description="Web搜索技能",
                body="搜索内容",
                path=Path("test"),
            )
        ]

        boosted = self.reuser.boost_skill_routing(skills, "搜索信息")
        self.assertEqual(len(boosted), 1)
        # 分数应该不变
        self.assertEqual(boosted[0].routing_score, 0)

    def test_update_usage_stats(self) -> None:
        """测试使用统计更新。"""
        experiences = [
            MemoryRecord(
                namespace="procedures",
                key="test1",
                content="内容",
            )
        ]

        self.reuser.update_usage_stats(experiences)
        self.mock_store.update_memory_stats.assert_called_once_with("procedures", "test1")


if __name__ == "__main__":
    unittest.main()
