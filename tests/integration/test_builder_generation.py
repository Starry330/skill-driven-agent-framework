from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent_framework.agents import create_builder_agent
from agent_framework.builders import AgentBlueprint, BuilderService, SkillBlueprint, ToolBlueprint
from agent_framework.config.settings import FrameworkSettings
from agent_framework.core import Gateway


class StaticChatModel(FakeListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # type: ignore[override]
        return self


class BuilderEnvelopeChatModel(StaticChatModel):
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        super().__init__(responses=[json.dumps(payload, ensure_ascii=False) for payload in payloads])


class BuilderGenerationIntegrationTest(unittest.TestCase):
    def _build_blueprint(self) -> AgentBlueprint:
        return AgentBlueprint(
            agent_id="generated_demo",
            name="Generated Demo",
            role="Generated Assistant",
            goal="回答简单演示问题。",
            workspace_docs={
                "agents_md": "# Agent Rules\n- Follow the generated demo workflow.",
                "soul_md": "# Role\nGenerated Assistant",
                "tools_md": "# Tools\n- calculator\n- demo_reply",
                "user_md": "# User\nGenerated demo user",
                "memory_md": "# Memory\nGenerated demo memory seed",
            },
            tool_plan=[
                ToolBlueprint(
                    name="calculator",
                    reuse_existing=True,
                    existing_tool_name="calculator",
                    description="Run simple arithmetic.",
                    reason="Built-in calculator covers arithmetic needs.",
                    io_schema={"input": {"expression": "string"}, "output": {"result": "string"}},
                    risk_level="low",
                ),
                ToolBlueprint(
                    name="demo_reply",
                    reuse_existing=False,
                    description="Reply with a short generated answer.",
                    reason="Need a dedicated generated reply tool.",
                    io_schema={"input": {"question": "string"}, "output": {"response": "string"}},
                    risk_level="low",
                    implementation_code="""
@tool
def demo_reply(question: str) -> str:
    \"\"\"Return a short generated answer.\"\"\"

    return f\"builder 生成的回答: {question}\"
""".strip(),
                ),
            ],
            skills=[
                SkillBlueprint(
                    name="demo-generation",
                    description="Answer demo prompts with demo_reply.",
                    body="Use `demo_reply` when the user asks a demo question.",
                    triggers=["演示", "demo"],
                    required_tools=["demo_reply"],
                    input_schema={"type": "object"},
                    output_schema={"type": "string"},
                    decision_logic=[{"else": "use_tool"}],
                    constraints=["Keep answers concise."],
                    failure_modes=[{"case": "tool_error", "effect": "cannot answer"}],
                    fallback_strategy=[{"when": "tool_error", "action": "report limitation"}],
                    tool_policy={"audit_logging": True},
                )
            ],
            tool_policy={
                "allowlist": ["calculator", "demo_reply"],
                "skill_tool_overrides": {"demo-generation": ["demo_reply"]},
            },
        )

    def _build_settings(self, root: Path) -> FrameworkSettings:
        return FrameworkSettings(
            workspace_root=root,
            storage_root=root / "storage",
            database_path=root / "storage" / "runtime.db",
        )

    def test_builder_agent_registers_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._build_settings(Path(temp_dir))
            gateway = Gateway(settings)
            llm = StaticChatModel(responses=["builder 已准备好接收创建需求。"])
            spec, tools = create_builder_agent(llm, gateway.settings)
            gateway.register_agent(spec, tools)

            response = gateway.run(agent_id="builder", user_input="帮我创建一个新 agent", session_id="builder-test")
            self.assertTrue(response)

    def test_builder_collects_requirements_before_designing_blueprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = self._build_settings(root)
            gateway = Gateway(settings)
            llm = BuilderEnvelopeChatModel(
                [
                    {
                        "action": "collect_requirements",
                        "payload": {
                            "agent_name": "Interview Coach",
                            "role": "面试辅导助手",
                            "goal": "帮助用户进行技术面试准备。",
                            "required_skills": ["question-generation"],
                            "required_tools": ["question_generator"],
                        },
                        "user_message": "已收集当前 requirements。",
                    }
                ]
            )
            spec, tools = create_builder_agent(llm, gateway.settings)
            gateway.register_agent(spec, tools)

            response = gateway.run(
                agent_id="builder",
                user_input="帮我创建一个面试辅导 agent",
                session_id="builder-requirements-only",
            )
            self.assertIn("requirements", response)
            self.assertNotIn("确认创建", response)

            state = gateway.session_manager.load_state("builder-requirements-only")
            builder_state = state.working_state.get("builder", {})
            self.assertEqual(builder_state.get("stage"), "requirements_collected")
            self.assertIsNotNone(builder_state.get("pending_requirements"))
            self.assertIsNone(builder_state.get("pending_blueprint"))
            self.assertIn("collect-agent-requirements", state.active_skills)

    def test_builder_designs_blueprint_after_requirements_then_confirms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = self._build_settings(root)
            gateway = Gateway(settings)
            llm = BuilderEnvelopeChatModel(
                [
                    {
                        "action": "collect_requirements",
                        "payload": {
                            "agent_name": "Generated Demo",
                            "agent_id": "generated_demo",
                            "role": "Generated Assistant",
                            "goal": "回答简单演示问题。",
                            "required_skills": ["demo-generation"],
                            "required_tools": ["calculator", "demo_reply"],
                        },
                        "user_message": "requirements 已收集完成。",
                    },
                    {
                        "action": "design_blueprint",
                        "payload": self._build_blueprint().model_dump(mode="json"),
                        "user_message": "已根据 requirements 生成 blueprint。",
                    },
                ]
            )
            spec, tools = create_builder_agent(llm, gateway.settings)
            gateway.register_agent(spec, tools)

            session_id = "builder-confirm-session"
            first_response = gateway.run(
                agent_id="builder",
                user_input="帮我创建一个演示 agent",
                session_id=session_id,
            )
            self.assertIn("requirements", first_response)

            second_response = gateway.run(
                agent_id="builder",
                user_input="继续设计 blueprint",
                session_id=session_id,
            )
            self.assertIn("确认创建", second_response)

            state = gateway.session_manager.load_state(session_id)
            builder_state = state.working_state.get("builder", {})
            self.assertEqual(builder_state.get("stage"), "awaiting_confirmation")
            self.assertTrue(builder_state.get("awaiting_confirmation"))
            self.assertIsNotNone(builder_state.get("pending_blueprint"))

            third_response = gateway.run(
                agent_id="builder",
                user_input="确认创建",
                session_id=session_id,
            )
            self.assertIn("generated_demo", third_response)
            self.assertTrue((root / "agent_framework" / "agents" / "generated_demo" / "spec.py").exists())

            state_after = gateway.session_manager.load_state(session_id)
            self.assertFalse(state_after.working_state.get("builder", {}).get("awaiting_confirmation", True))

    def test_builder_requirement_change_invalidates_existing_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = self._build_settings(root)
            gateway = Gateway(settings)
            llm = BuilderEnvelopeChatModel(
                [
                    {
                        "action": "collect_requirements",
                        "payload": {
                            "agent_name": "Generated Demo",
                            "agent_id": "generated_demo",
                            "role": "Generated Assistant",
                            "goal": "回答简单演示问题。",
                            "required_skills": ["demo-generation"],
                            "required_tools": ["calculator", "demo_reply"],
                        },
                        "user_message": "requirements 已收集完成。",
                    },
                    {
                        "action": "design_blueprint",
                        "payload": self._build_blueprint().model_dump(mode="json"),
                        "user_message": "已根据 requirements 生成 blueprint。",
                    },
                    {
                        "action": "collect_requirements",
                        "payload": {
                            "agent_name": "Generated Demo",
                            "agent_id": "generated_demo",
                            "role": "Generated Assistant",
                            "goal": "回答更严格的演示问题。",
                            "required_skills": ["demo-generation"],
                            "required_tools": ["calculator", "demo_reply"],
                        },
                        "user_message": "requirements 已更新。",
                    },
                ]
            )
            spec, tools = create_builder_agent(llm, gateway.settings)
            gateway.register_agent(spec, tools)

            session_id = "builder-requirements-reset"
            gateway.run(agent_id="builder", user_input="先收集需求", session_id=session_id)
            gateway.run(agent_id="builder", user_input="设计 blueprint", session_id=session_id)
            state_ready = gateway.session_manager.load_state(session_id)
            self.assertTrue(state_ready.working_state.get("builder", {}).get("awaiting_confirmation"))

            response = gateway.run(agent_id="builder", user_input="我改一下目标", session_id=session_id)
            self.assertIn("requirements", response)

            state_after = gateway.session_manager.load_state(session_id)
            builder_state = state_after.working_state.get("builder", {})
            self.assertEqual(builder_state.get("stage"), "requirements_collected")
            self.assertFalse(builder_state.get("awaiting_confirmation"))
            self.assertIsNone(builder_state.get("pending_blueprint"))

    def test_builder_runtime_ask_more_info_does_not_create_pending_blueprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = self._build_settings(root)
            gateway = Gateway(settings)
            llm = BuilderEnvelopeChatModel(
                [
                    {
                        "action": "ask_more_info",
                        "payload": {},
                        "user_message": "还缺少角色定位和工具需求，请继续补充。",
                    }
                ]
            )
            spec, tools = create_builder_agent(llm, gateway.settings)
            gateway.register_agent(spec, tools)

            response = gateway.run(
                agent_id="builder",
                user_input="帮我创建一个面试 agent",
                session_id="builder-runtime-ask-more-info",
            )
            self.assertIn("还缺少角色定位和工具需求", response)
            self.assertNotIn("确认创建", response)

            state = gateway.session_manager.load_state("builder-runtime-ask-more-info")
            self.assertIsNone(state.working_state.get("builder", {}).get("pending_blueprint"))

    def test_generated_agent_can_run_through_gateway(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = BuilderService(root)
            blueprint = self._build_blueprint()
            service.generate_from_blueprint(blueprint)

            spec_path = root / "agent_framework" / "agents" / "generated_demo" / "spec.py"
            agent_dir = spec_path.parent

            sys.path.insert(0, str(agent_dir))
            try:
                module_spec = importlib.util.spec_from_file_location("generated_demo_spec", spec_path)
                self.assertIsNotNone(module_spec)
                self.assertIsNotNone(module_spec.loader)
                module = importlib.util.module_from_spec(module_spec)
                assert module_spec.loader is not None
                module_spec.loader.exec_module(module)
                factory = getattr(module, "create_generated_demo_agent")

                settings = self._build_settings(root)
                gateway = Gateway(settings)
                llm = StaticChatModel(responses=["这是生成 agent 的测试响应。"])
                spec, tools = factory(llm, settings)
                gateway.register_agent(spec, tools)

                self.assertTrue(spec.requires_active_skill)
                response = gateway.run(
                    agent_id="generated_demo",
                    user_input="请做一个演示回答",
                    session_id="generated-demo-session",
                )
                self.assertEqual(response, "这是生成 agent 的测试响应。")
            finally:
                if sys.path and sys.path[0] == str(agent_dir):
                    sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
