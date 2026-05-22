"""记忆沉淀机制演示脚本。

演示完整的闭环流程：执行→反思→提炼→分类存储→索引更新→按需复用
"""

import json
import tempfile
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_framework.memory.long_term_memory.sqlite import SQLiteLongTermMemoryStore
from agent_framework.memory.manager import MemoryManager
from agent_framework.memory.reflection.distiller import ExperienceDistiller
from agent_framework.memory.reflection.engine import ReflectionEngine
from agent_framework.memory.reuse.retriever import ExperienceReuser
from agent_framework.memory.short_term_memory.sqlite import SQLiteShortTermMemoryStore


class DemoLLM:
    """演示用的假LLM，返回预设的反思结果。"""

    def __init__(self):
        self.call_count = 0

    def invoke(self, messages):
        # 第一次调用返回反思结果
        if self.call_count == 0:
            self.call_count += 1
            reflection = {
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
            return type("Response", (), {"content": json.dumps(reflection)})()
        return type("Response", (), {"content": "{}"})()


def main():
    print("=" * 60)
    print("记忆沉淀机制演示")
    print("=" * 60)

    # 创建临时数据库
    temp_dir = tempfile.mkdtemp()
    db_path = str(Path(temp_dir) / "demo.db")

    # 初始化存储
    short_term_store = SQLiteShortTermMemoryStore(db_path)
    long_term_store = SQLiteLongTermMemoryStore(db_path)
    memory_manager = MemoryManager(short_term_store, long_term_store)

    llm = DemoLLM()

    # ==================== 第1轮：执行任务 ====================
    print("\n【第1轮】执行任务：创建研究Agent")
    print("-" * 40)

    # 模拟对话
    messages = [
        HumanMessage(content="帮我创建一个研究Agent"),
        AIMessage(content="好的，我来帮你创建研究Agent。首先收集需求..."),
        ToolMessage(content="需求收集完成：需要web搜索功能", tool_call_id="tool_1"),
        AIMessage(content="需求已收集，现在设计蓝图..."),
        ToolMessage(content="蓝图设计完成", tool_call_id="tool_2"),
        AIMessage(content="研究Agent创建成功！"),
    ]

    # 执行反思
    print("  [1/4] 执行反思引擎...")
    engine = ReflectionEngine(llm)
    reflection = engine.reflect(messages, "创建研究Agent")
    print(f"        结果：outcome={reflection.outcome}")
    print(f"        程序性经验：{len(reflection.procedures)}条")
    print(f"        情景记忆：{len(reflection.episodes)}条")
    print(f"        用户偏好：{len(reflection.preferences)}条")

    # 提炼经验
    print("\n  [2/4] 执行经验提炼器...")
    distiller = ExperienceDistiller(long_term_store)
    records = distiller.distill(reflection)
    print(f"        提炼出{len(records)}条记忆记录")
    for record in records:
        print(f"          - [{record.namespace}] {record.experience_type}")

    # 存储经验
    print("\n  [3/4] 存储经验到数据库...")
    import uuid
    for record in records:
        record.key = str(uuid.uuid4())
        long_term_store.store(record)
    print(f"        已存储{len(records)}条经验")

    # 验证存储
    print("\n  [4/4] 验证存储...")
    procedures = memory_manager.retrieve("创建Agent", ["procedures"])
    episodes = memory_manager.retrieve("研究Agent", ["episodes"])
    print(f"        procedures命名空间：{len(procedures)}条")
    print(f"        episodes命名空间：{len(episodes)}条")

    # ==================== 第2轮：复用经验 ====================
    print("\n" + "=" * 60)
    print("【第2轮】复用经验：用户再次请求创建Agent")
    print("-" * 40)

    user_input = "帮我创建一个FEA Agent"

    # 检索相关经验
    print("\n  [1/3] 检索相关经验...")
    reuser = ExperienceReuser(long_term_store)
    all_experiences = reuser.retrieve_experiences(user_input, ["procedures", "episodes", "user_preferences"])
    print(f"        找到{len(all_experiences)}条相关经验")

    # 格式化经验
    print("\n  [2/3] 格式化经验为prompt注入...")
    formatted = reuser.format_experiences_for_prompt(all_experiences)
    if formatted:
        print("        格式化结果：")
        for line in formatted.split("\n")[:5]:
            print(f"          {line}")
    else:
        print("        (无相关经验)")

    # 技能路由
    print("\n  [3/3] 技能路由（带经验提升）...")
    from agent_framework.skills.models import SkillSpec
    from agent_framework.tools.policy import ToolPolicy

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

    boosted = reuser.boost_skill_routing(skills, user_input)
    for skill in boosted:
        print(f"        {skill.name}: routing_score={skill.routing_score}")

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
    print("[VALUE] 核心价值：")
    print("  - 执行-反思-提炼-存储-索引-复用 闭环")
    print("  - 跨会话经验复用")
    print("  - Skill能力持续生长")
    print("=" * 60)

    # 清理
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
