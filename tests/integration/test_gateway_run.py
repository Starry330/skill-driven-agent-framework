import unittest
from pathlib import Path
import tempfile

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessageChunk

from agent_framework.agents import create_research_agent
from agent_framework.config.settings import FrameworkSettings
from agent_framework.core import Gateway


class StaticChatModel(FakeListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # type: ignore[override]
        return self


class ExplodingChatModel(StaticChatModel):
    def invoke(self, input, config=None, **kwargs):  # type: ignore[override]
        raise AssertionError("LLM should not be called when no active skill is available")

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # type: ignore[override]
        raise AssertionError("Tools should not be bound when no active skill is available")


class StreamingStaticChatModel(StaticChatModel):
    def __init__(self, response_text: str) -> None:
        super().__init__(responses=[response_text])
        object.__setattr__(self, "_response_text", response_text)

    def stream(self, input, config=None, **kwargs):  # type: ignore[override]
        response_text = getattr(self, "_response_text")
        midpoint = max(1, len(response_text) // 2)
        yield AIMessageChunk(content=response_text[:midpoint])
        # 用累计文本模拟部分 provider 的 stream 语义。
        yield AIMessageChunk(content=response_text)


class GatewayIntegrationTest(unittest.TestCase):
    def test_gateway_run_returns_model_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = FrameworkSettings(
                storage_root=Path(temp_dir),
                database_path=Path(temp_dir) / "runtime.db",
                web_search_url="http://example.test/search",
            )
            gateway = Gateway(settings)
            llm = StaticChatModel(responses=["这是一个测试响应。"])
            spec, tools = create_research_agent(llm, gateway.settings)
            gateway.register_agent(spec, tools)

            response = gateway.run(agent_id="research", user_input="请搜索测试主题", session_id="test-session")
            self.assertEqual(response, "这是一个测试响应。")

    def test_gateway_run_without_active_skill_does_not_call_llm(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = FrameworkSettings(
                storage_root=Path(temp_dir),
                database_path=Path(temp_dir) / "runtime.db",
            )
            gateway = Gateway(settings)
            spec, tools = create_research_agent(ExplodingChatModel(responses=["unused"]), gateway.settings)
            gateway.register_agent(spec, tools)

            response = gateway.run(agent_id="research", user_input="你好", session_id="no-skill-session")

            self.assertIn("抱歉", response)

    def test_gateway_stream_yields_text_delta_and_persists_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = FrameworkSettings(
                storage_root=Path(temp_dir),
                database_path=Path(temp_dir) / "runtime.db",
                web_search_url="http://example.test/search",
            )
            gateway = Gateway(settings)
            llm = StreamingStaticChatModel("<think>内部推理</think>流式响应测试。")
            spec, tools = create_research_agent(llm, gateway.settings)
            gateway.register_agent(spec, tools)

            events = list(gateway.stream(agent_id="research", user_input="请搜索测试主题", session_id="stream-session"))
            text_deltas = [event.payload["text"] for event in events if event.event_type == "text_delta"]
            self.assertEqual("".join(text_deltas), "流式响应测试。")

            completed_events = [event for event in events if event.event_type == "run_completed"]
            self.assertEqual(len(completed_events), 1)
            self.assertEqual(completed_events[0].payload["response_text"], "流式响应测试。")

            state = gateway.session_manager.load_state("stream-session")
            self.assertEqual(state.summary, "")
            self.assertEqual(state.working_state, {})

            messages = gateway.session_manager.load_messages("stream-session")
            self.assertEqual(len(messages), 2)


if __name__ == "__main__":
    unittest.main()
