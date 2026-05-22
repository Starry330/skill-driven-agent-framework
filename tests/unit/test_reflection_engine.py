"""test_reflection_engine.py — 反思引擎单元测试。"""

import json
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_framework.memory.reflection.engine import ReflectionEngine


class _FakeLLM:
    """返回预设响应的假 LLM。"""

    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, messages):  # noqa: ANN001
        return MagicMock(content=self._content)


class ReflectionEngineTest(unittest.TestCase):
    def test_reflect_with_valid_response(self) -> None:
        """测试有效的反思响应解析。"""
        response_data = {
            "outcome": "success",
            "procedures": [
                {
                    "task_pattern": "创建Agent",
                    "steps": ["收集需求", "设计蓝图", "生成脚手架"],
                    "content": "创建Agent的完整流程",
                    "confidence": 0.7,
                }
            ],
            "episodes": [
                {
                    "context_summary": "用户要求创建研究Agent",
                    "outcome": "success",
                    "key_factors": ["需求明确", "工具可用"],
                    "content": "成功创建研究Agent的案例",
                    "confidence": 0.8,
                }
            ],
            "preferences": [
                {
                    "category": "language",
                    "content": "用户偏好中文交流",
                    "evidence": ["用户全程使用中文"],
                    "confidence": 0.9,
                }
            ],
            "lessons": ["需求收集阶段要充分"],
        }
        llm = _FakeLLM(json.dumps(response_data))
        engine = ReflectionEngine(llm)

        messages = [
            HumanMessage(content="创建一个研究Agent"),
            AIMessage(content="好的，我来帮你创建"),
            ToolMessage(content="Agent创建成功", tool_call_id="test_id"),
        ]

        result = engine.reflect(messages, "创建研究Agent")

        self.assertIsNotNone(result)
        self.assertEqual(result.outcome, "success")
        self.assertEqual(len(result.procedures), 1)
        self.assertEqual(len(result.episodes), 1)
        self.assertEqual(len(result.preferences), 1)
        self.assertEqual(len(result.lessons), 1)

    def test_reflect_with_short_messages(self) -> None:
        """测试消息数量不足时返回None。"""
        llm = _FakeLLM("should not be called")
        engine = ReflectionEngine(llm)

        messages = [HumanMessage(content="hello")]
        result = engine.reflect(messages)

        self.assertIsNone(result)

    def test_reflect_with_invalid_json(self) -> None:
        """测试无效JSON响应处理。"""
        llm = _FakeLLM("not json at all")
        engine = ReflectionEngine(llm)

        messages = [
            HumanMessage(content="hello"),
            AIMessage(content="hi"),
            ToolMessage(content="result", tool_call_id="test_id"),
        ]

        result = engine.reflect(messages)
        self.assertIsNone(result)

    def test_reflect_with_markdown_fences(self) -> None:
        """测试带markdown代码块的响应解析。"""
        response_data = {
            "outcome": "partial",
            "procedures": [],
            "episodes": [],
            "preferences": [],
            "lessons": ["部分完成"],
        }
        fenced = f"```json\n{json.dumps(response_data)}\n```"
        llm = _FakeLLM(fenced)
        engine = ReflectionEngine(llm)

        messages = [
            HumanMessage(content="hello"),
            AIMessage(content="hi"),
            ToolMessage(content="result", tool_call_id="test_id"),
        ]

        result = engine.reflect(messages)
        self.assertIsNotNone(result)
        self.assertEqual(result.outcome, "partial")

    def test_format_conversation(self) -> None:
        """测试对话格式化。"""
        llm = _FakeLLM("{}")
        engine = ReflectionEngine(llm)

        messages = [
            HumanMessage(content="user message"),
            AIMessage(content="ai response"),
            ToolMessage(content="tool result", tool_call_id="test_id"),
        ]

        conversation = engine._format_conversation(messages)
        self.assertIn("human: user message", conversation)
        self.assertIn("ai: ai response", conversation)
        self.assertIn("tool_result: tool result", conversation)

    def test_extract_tool_results(self) -> None:
        """测试工具结果提取。"""
        llm = _FakeLLM("{}")
        engine = ReflectionEngine(llm)

        messages = [
            HumanMessage(content="hello"),
            ToolMessage(content="result 1", tool_call_id="test_id_1"),
            AIMessage(content="response"),
            ToolMessage(content="result 2", tool_call_id="test_id_2"),
        ]

        tool_results = engine._extract_tool_results(messages)
        self.assertIn("result 1", tool_results)
        self.assertIn("result 2", tool_results)


if __name__ == "__main__":
    unittest.main()
