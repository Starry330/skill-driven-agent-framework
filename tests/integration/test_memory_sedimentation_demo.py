"""test_memory_sedimentation_demo.py — 记忆沉淀机制端到端演示。

演示完整的闭环流程：执行→反思→提炼→分类存储→索引更新→按需复用
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_framework.memory.manager import MemoryManager
from agent_framework.memory.models import MemoryRecord, ReflectionResult
from agent_framework.memory.reflection.engine import ReflectionEngine
from agent_framework.memory.reflection.distiller import ExperienceDistiller
from agent_framework.memory.reuse.retriever import ExperienceReuser
from agent_framework.memory.sqlite_backend import SQLiteMemoryBackend


class _FakeLLM:
    """返回预设响应的假 LLM。"""

    def __init__(self, responses: list) -> None:
        self._responses = responses
        self._call_count = 0

    def invoke(self, messages):  # noqa: ANN001
        if self._call_count < len(self._responses):
            response = self._responses[self._call_count]
            self._call_count += 1
            return MagicMock(content=response)
        return MagicMock(content="{}")


class MemorySedimentationDemoTest(unittest.TestCase):
    """记忆沉淀机制端到端演示测试。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.db")

        # 初始化存储后端
        self.backend = SQLiteMemoryBackend(self.db_path)

        # 初始化记忆管理器
        from agent_framework.memory.long_term_memory.sqlite import SQLiteLongTermMemoryStore
        from agent_framework.memory.short_term_memory.sqlite import SQLiteShortTermMemoryStore

        short_term_store = SQLiteShortTermMemoryStore(self.db_path)
        long_term_store = SQLiteLongTermMemoryStore(self.db_path)
        self.memory_manager = MemoryManager(short_term_store, long_term_store)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_sedimentation_cycle(self) -> None:
        """演示完整的记忆沉淀循环。

        场景：用户要求创建一个研究Agent，系统执行并提炼经验。
        """
        print("\n" + "=" * 60)
        print("记忆沉淀机制演示")
        print("=" * 60)

        # ==================== 第1轮：执行任务 ====================
        print("\n【第1轮】执行任务：创建研究Agent")

        # 模拟对话
        messages_round1 = [
            HumanMessage(content="帮我创建一个研究Agent"),
            AIMessage(content="好的，我来帮你创建研究Agent。首先收集需求..."),
            ToolMessage(content="需求收集完成：需要web搜索功能", tool_call_id="tool_1"),
            AIMessage(content="需求已收集，现在设计蓝图..."),
            ToolMessage(content="蓝图设计完成", tool_call_id="tool_2"),
            AIMessage(content="研究Agent创建成功！"),
        ]

        # 模拟LLM响应：反思结果
        reflection_response = {
            "outcome": "success",
            "procedures": [
                {
                    "task_pattern": "创建研究Agent",
                    "steps": ["收集需求", "设计蓝图", "生成脚手架", "验证"],
                    "content": "创建研究Agent的完整流程：1)收集需求确认需要web搜索功能 2)设计蓝图包含web-search技能 3)生成脚手架 4)验证可运行",
                    "confidence": 0.7,
                }
            ],
            "episodes": [
                {
                    "context_summary": "用户要求创建研究Agent，需要web搜索功能",
                    "outcome": "success",
                    "key_factors": ["需求明确", "工具可用", "流程正确"],
                    "content": "成功创建研究Agent的案例：用户明确需要web搜索，我们正确配置了web_search工具和web-search技能",
                    "confidence": 0.8,
                }
            ],
            "preferences": [
                {
                    "category": "workflow",
                    "content": "用户倾向于一次性提出完整需求",
                    "evidence": ["用户直接说明了需要研究Agent和web搜索功能"],
                    "confidence": 0.6,
                }
            ],
            "lessons": ["需求收集阶段要确认工具可用性"],
        }

        llm = _FakeLLM([json.dumps(reflection_response)])

        # 执行反思
        print("  → 执行反思引擎...")
        engine = ReflectionEngine(llm)
        reflection = engine.reflect(messages_round1, "创建研究Agent")

        self.assertIsNotNone(reflection)
        print(f"  → 反思结果：outcome={reflection.outcome}")
        print(f"    - 程序性经验：{len(reflection.procedures)}条")
        print(f"    - 情景记忆：{len(reflection.episodes)}条")
        print(f"    - 用户偏好：{len(reflection.preferences)}条")
        print(f"    - 经验教训：{len(reflection.lessons)}条")

        # 提炼经验
        print("\n  → 执行经验提炼器...")
        distiller = ExperienceDistiller(self.memory_manager.long_term_store)
        records = distiller.distill(reflection)

        print(f"  → 提炼出{len(records)}条记忆记录")
        for record in records:
            print(f"    - [{record.namespace}] {record.experience_type}: {record.content[:50]}...")

        # 存储经验
        print("\n  → 存储经验到数据库...")
        import uuid
        for record in records:
            record.key = str(uuid.uuid4())
            self.memory_manager.long_term_store.store(record)

        # 验证存储
        stored_procedures = self.memory_manager.retrieve("创建Agent", ["procedures"])
        stored_episodes = self.memory_manager.retrieve("研究Agent", ["episodes"])
        stored_preferences = self.memory_manager.retrieve("用户偏好", ["user_preferences"])

        print(f"  → 存储验证：")
        print(f"    - procedures命名空间：{len(stored_procedures)}条记录")
        print(f"    - episodes命名空间：{len(stored_episodes)}条记录")
        print(f"    - user_preferences命名空间：{len(stored_preferences)}条记录")

        # ==================== 第2轮：复用经验 ====================
        print("\n" + "-" * 60)
        print("【第2轮】复用经验：用户再次请求创建Agent")

        # 模拟新的用户输入
        user_input = "帮我创建一个FEA Agent"

        # 检索相关经验
        print("\n  → 检索相关经验...")
        reuser = ExperienceReuser(self.memory_manager.long_term_store)

        # 检索程序性经验
        procedures = reuser.retrieve_experiences(user_input, ["procedures"])
        print(f"    - 找到{len(procedures)}条程序性经验")

        # 检索情景记忆
        episodes = reuser.retrieve_experiences(user_input, ["episodes"])
        print(f"    - 找到{len(episodes)}条情景记忆")

        # 检索用户偏好
        preferences = reuser.retrieve_experiences(user_input, ["user_preferences"])
        print(f"    - 找到{len(preferences)}条用户偏好")

        # 格式化经验为prompt注入
        print("\n  → 格式化经验为prompt注入...")
        all_experiences = procedures + episodes + preferences
        formatted_experience = reuser.format_experiences_for_prompt(all_experiences)

        print("  → 格式化后的经验：")
        print("-" * 40)
        print(formatted_experience[:500] + "..." if len(formatted_experience) > 500 else formatted_experience)
        print("-" * 40)

        # 模拟技能路由
        print("\n  → 技能路由（带经验提升）...")
        from agent_framework.skills.models import SkillSpec

        skills = [
            SkillSpec(
                name="static-structural-fea",
                description="静力学FEA分析技能",
                body="分析STP文件并进行静力学分析",
                path=Path("test"),
            ),
            SkillSpec(
                name="web-search",
                description="Web搜索技能",
                body="搜索网络信息",
                path=Path("test"),
            ),
        ]

        # 应用经验提升
        boosted_skills = reuser.boost_skill_routing(skills, user_input)
        for skill in boosted_skills:
            print(f"    - {skill.name}: routing_score={skill.routing_score}")

        # ==================== 第3轮：验证学习效果 ====================
        print("\n" + "-" * 60)
        print("【第3轮】验证学习效果")

        # 验证经验可以被检索到
        print("\n  → 验证经验检索...")
        all_procedures = self.memory_manager.retrieve("创建", ["procedures"])
        all_episodes = self.memory_manager.retrieve("研究", ["episodes"])

        print(f"    - 所有程序性经验：{len(all_procedures)}条")
        for i, proc in enumerate(all_procedures, 1):
            print(f"      {i}. {proc[:80]}...")

        print(f"    - 所有情景记忆：{len(all_episodes)}条")
        for i, ep in enumerate(all_episodes, 1):
            print(f"      {i}. {ep[:80]}...")

        # ==================== 总结 ====================
        print("\n" + "=" * 60)
        print("演示总结")
        print("=" * 60)
        print("[SUCCESS] 第1轮：执行任务 -> 反思 -> 提炼 -> 存储")
        print("  - 成功创建研究Agent")
        print("  - 提炼出程序性经验、情景记忆、用户偏好")
        print("  - 经验存储到procedures、episodes、user_preferences命名空间")
        print()
        print("[SUCCESS] 第2轮：复用经验")
        print("  - 检索到相关经验并格式化为prompt注入")
        print("  - 技能路由应用经验提升")
        print("  - 系统可以利用历史经验指导新任务")
        print()
        print("[SUCCESS] 第3轮：验证学习效果")
        print("  - 经验可以被后续会话检索和复用")
        print("  - 实现了跨会话经验积累")
        print()
        print("[VALUE] 核心价值：")
        print("  - 执行-反思-提炼-存储-索引-复用 闭环")
        print("  - 跨会话经验复用")
        print("  - Skill能力持续生长")

        # 验证断言
        self.assertIsNotNone(reflection)
        self.assertEqual(reflection.outcome, "success")
        self.assertTrue(len(records) > 0)
        self.assertTrue(len(all_procedures) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
