"""test_tool_visibility.py — 动态工具可见性和验证节点单元测试。"""

import unittest
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from agent_framework.tools.executor import ToolExecutor, ToolExecutionError
from agent_framework.tools.models import ToolExecutionContext, ToolSpec
from agent_framework.tools.policy import ToolPolicy, ToolPolicyEngine
from agent_framework.tools.registry import ToolRegistry
from agent_framework.tools.validated_tool_node import validate_tool_calls


def _make_spec(name: str, description: str = "") -> ToolSpec:
    base = StructuredTool.from_function(func=lambda: None, name=name, description=description)
    return ToolSpec(name=name, description=description or f"{name} tool", base_tool=base)


class BuildFilteredLangchainToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.spec_a = _make_spec("tool_a")
        self.spec_b = _make_spec("tool_b")
        self.spec_c = _make_spec("tool_c")
        self.registry.register(self.spec_a)
        self.registry.register(self.spec_b)
        self.registry.register(self.spec_c)

        self.executor = ToolExecutor(
            registry=self.registry,
            policy_engine=ToolPolicyEngine(),
            approval_manager=MagicMock(),
            audit_logger=MagicMock(),
        )
        self.context = ToolExecutionContext(
            agent_id="test",
            session_id="s1",
            active_skills=["skill_1"],
            requires_active_skill=False,
        )

    def test_global_tools_always_visible(self) -> None:
        """不在任何 override 中的工具始终可见。"""
        policy = ToolPolicy(allowlist=["tool_a", "tool_b", "tool_c"])
        tools, names = self.executor.build_filtered_langchain_tools(
            self.context, policy, active_skills=[]
        )
        self.assertEqual(sorted(names), ["tool_a", "tool_b", "tool_c"])

    def test_skill_tools_only_when_active(self) -> None:
        """在 override 中的工具仅在对应 skill 激活时可见。"""
        policy = ToolPolicy(
            allowlist=["tool_a", "tool_b", "tool_c"],
            skill_tool_overrides={"skill_1": ["tool_a"], "skill_2": ["tool_b"]},
        )
        # skill_1 激活 → tool_a 可见，tool_b 不可见
        tools, names = self.executor.build_filtered_langchain_tools(
            self.context, policy, active_skills=["skill_1"]
        )
        self.assertIn("tool_a", names)
        self.assertNotIn("tool_b", names)
        self.assertIn("tool_c", names)  # 全局工具

    def test_multiple_active_skills_union(self) -> None:
        """多个 skill 同时激活时，取并集。"""
        policy = ToolPolicy(
            allowlist=["tool_a", "tool_b", "tool_c"],
            skill_tool_overrides={"skill_1": ["tool_a"], "skill_2": ["tool_b"]},
        )
        tools, names = self.executor.build_filtered_langchain_tools(
            self.context, policy, active_skills=["skill_1", "skill_2"]
        )
        self.assertIn("tool_a", names)
        self.assertIn("tool_b", names)
        self.assertIn("tool_c", names)

    def test_empty_overrides_shows_all(self) -> None:
        """没有 override 时所有允许的工具都可见。"""
        policy = ToolPolicy(allowlist=["tool_a", "tool_b", "tool_c"])
        tools, names = self.executor.build_filtered_langchain_tools(
            self.context, policy, active_skills=[]
        )
        self.assertEqual(len(names), 3)


class ValidateToolCallsTest(unittest.TestCase):
    def test_all_valid_passes_through(self) -> None:
        state = {
            "visible_tool_names": ["a", "b"],
            "messages": [AIMessage(content="", tool_calls=[{"id": "1", "name": "a", "args": {}}])],
        }
        expected = {"messages": [ToolMessage(content="ok", tool_call_id="1", name="a")]}
        fn = MagicMock(return_value=expected)

        result = validate_tool_calls(state, fn)

        fn.assert_called_once_with(state)
        self.assertEqual(result, expected)

    def test_intercepts_illegal_calls(self) -> None:
        state = {
            "visible_tool_names": ["a"],
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "1", "name": "a", "args": {}},
                        {"id": "2", "name": "c", "args": {}},
                    ],
                )
            ],
        }
        fn = MagicMock(return_value={"messages": [ToolMessage(content="ok", tool_call_id="1", name="a")]})

        result = validate_tool_calls(state, fn)

        # fn 只应被调用一次（混合场景）
        fn.assert_called_once()
        messages = result["messages"]
        # 应有 1 个正常结果 + 1 个错误消息
        self.assertEqual(len(messages), 2)
        error_msgs = [m for m in messages if "not available" in m.content]
        self.assertEqual(len(error_msgs), 1)
        self.assertEqual(error_msgs[0].tool_call_id, "2")

    def test_all_invalid_returns_errors_only(self) -> None:
        state = {
            "visible_tool_names": ["a"],
            "messages": [
                AIMessage(content="", tool_calls=[{"id": "1", "name": "c", "args": {}}])
            ],
        }
        fn = MagicMock()

        result = validate_tool_calls(state, fn)

        fn.assert_not_called()
        messages = result["messages"]
        self.assertEqual(len(messages), 1)
        self.assertIn("not available", messages[0].content)

    def test_no_visible_tools_skips_validation(self) -> None:
        """visible_tool_names 为空时不做验证。"""
        state = {
            "messages": [
                AIMessage(content="", tool_calls=[{"id": "1", "name": "any", "args": {}}])
            ],
        }
        fn = MagicMock(return_value={"messages": []})

        validate_tool_calls(state, fn)

        fn.assert_called_once()

    def test_no_tool_calls_passes_through(self) -> None:
        state = {
            "visible_tool_names": ["a"],
            "messages": [AIMessage(content="hello")],
        }
        fn = MagicMock(return_value={})

        result = validate_tool_calls(state, fn)

        fn.assert_called_once_with(state)


if __name__ == "__main__":
    unittest.main()
