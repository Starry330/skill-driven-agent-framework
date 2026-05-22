"""test_memory_flush.py — flush_to_memory 单元测试。"""

import json
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from agent_framework.memory.flush import flush_to_memory


class _FakeLLM:
    """返回预设响应的假 LLM。"""

    def __init__(self, content: str) -> None:
        self._content = content

    def invoke(self, messages):  # noqa: ANN001
        return MagicMock(content=self._content)


class FlushToMemoryTest(unittest.TestCase):
    def test_extracts_facts(self) -> None:
        llm = _FakeLLM(json.dumps(["用户偏好深色主题", "项目路径为 /tmp/demo"]))
        mm = MagicMock()

        flush_to_memory(
            [HumanMessage(content="hello"), AIMessage(content="hi")],
            mm,
            llm,  # type: ignore[arg-type]
        )

        self.assertEqual(mm.write_memory.call_count, 2)
        # 验证写入到semantic命名空间，且包含metadata
        calls = mm.write_memory.call_args_list
        namespaces = [call.kwargs.get("namespace") or call.args[0] if call.args else call.kwargs.get("namespace") for call in calls]
        self.assertTrue(all(ns == "semantic" for ns in namespaces))
        # 验证包含metadata
        for call in calls:
            if call.kwargs:
                self.assertIn("metadata", call.kwargs)
                metadata = call.kwargs["metadata"]
                self.assertEqual(metadata["source"], "flush")
                self.assertEqual(metadata["confidence"], 0.6)

    def test_handles_markdown_fences(self) -> None:
        fenced = "```json\n[\"fact A\", \"fact B\"]\n```"
        llm = _FakeLLM(fenced)
        mm = MagicMock()

        flush_to_memory([HumanMessage(content="test")], mm, llm)  # type: ignore[arg-type]

        self.assertEqual(mm.write_memory.call_count, 2)

    def test_handles_bare_code_fences(self) -> None:
        fenced = "```\n[\"only fact\"]\n```"
        llm = _FakeLLM(fenced)
        mm = MagicMock()

        flush_to_memory([HumanMessage(content="test")], mm, llm)  # type: ignore[arg-type]

        mm.write_memory.assert_called_once_with(
            namespace="semantic",
            content="only fact",
            metadata={"source": "flush", "extracted_at": unittest.mock.ANY, "confidence": 0.6},
        )

    def test_empty_messages_noop(self) -> None:
        llm = _FakeLLM("should not be called")
        mm = MagicMock()

        flush_to_memory([], mm, llm)  # type: ignore[arg-type]

        mm.write_memory.assert_not_called()

    def test_invalid_json_is_swallowed(self) -> None:
        llm = _FakeLLM("not json at all")
        mm = MagicMock()

        # 不应抛出异常
        flush_to_memory([HumanMessage(content="test")], mm, llm)  # type: ignore[arg-type]

        mm.write_memory.assert_not_called()

    def test_non_array_json_is_ignored(self) -> None:
        llm = _FakeLLM(json.dumps({"key": "value"}))
        mm = MagicMock()

        flush_to_memory([HumanMessage(content="test")], mm, llm)  # type: ignore[arg-type]

        mm.write_memory.assert_not_called()

    def test_skips_empty_facts(self) -> None:
        llm = _FakeLLM(json.dumps(["valid", "", "  "]))
        mm = MagicMock()

        flush_to_memory([HumanMessage(content="test")], mm, llm)  # type: ignore[arg-type]

        mm.write_memory.assert_called_once_with(
            namespace="semantic",
            content="valid",
            metadata={"source": "flush", "extracted_at": unittest.mock.ANY, "confidence": 0.6},
        )


if __name__ == "__main__":
    unittest.main()
