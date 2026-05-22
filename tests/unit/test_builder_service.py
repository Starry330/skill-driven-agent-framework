from pathlib import Path
import tempfile
import unittest

from agent_framework.builders import (
    AgentBlueprint,
    AgentRequirements,
    BUILDER_CONFIRMATION_PHRASE,
    BuilderService,
    SkillBlueprint,
    ToolBlueprint,
)


class BuilderServiceTest(unittest.TestCase):
    def _build_requirements(self) -> AgentRequirements:
        return AgentRequirements(
            agent_name="Demo Agent",
            agent_id="demo_agent",
            role="Demo Assistant",
            goal="帮助用户完成简单演示任务。",
            style_constraints=["保持清晰", "输出简洁"],
            required_skills=["demo-skill"],
            required_tools=["calculator", "greet_topic"],
            user_constraints=["Only answer demo prompts."],
        )

    def _build_blueprint(self, agent_id: str = "demo_agent") -> AgentBlueprint:
        return AgentBlueprint(
            agent_id=agent_id,
            name="Demo Agent",
            role="Demo Assistant",
            goal="帮助用户完成简单演示任务。",
            style_constraints=["保持清晰", "输出简洁"],
            workspace_docs={
                "agents_md": "# Agent Rules\n- Follow the demo workflow.",
                "soul_md": "# Role\nDemo Assistant",
                "tools_md": "# Tools\n- calculator\n- greet_topic",
                "user_md": "# User\nDemo user",
                "memory_md": "# Memory\nDemo memory seed",
            },
            tool_plan=[
                ToolBlueprint(
                    name="calculator",
                    reuse_existing=True,
                    existing_tool_name="calculator",
                    description="Run simple arithmetic.",
                    reason="Built-in calculator already covers arithmetic needs.",
                    io_schema={"input": {"expression": "string"}, "output": {"result": "string"}},
                    risk_level="low",
                ),
                ToolBlueprint(
                    name="greet_topic",
                    reuse_existing=False,
                    description="Return a canned analysis response.",
                    reason="Need a dedicated demo response tool for generated agents.",
                    io_schema={"input": {"topic": "string"}, "output": {"response": "string"}},
                    risk_level="low",
                    implementation_code="""
@tool
def greet_topic(topic: str) -> str:
    \"\"\"Return a short response for the given topic.\"\"\"

    return f\"演示主题: {topic}\"
""".strip(),
                ),
            ],
            skills=[
                SkillBlueprint(
                    name="demo-skill",
                    description="Handle simple demo prompts.",
                    body="Use `greet_topic` when the user asks for a demo answer.",
                    triggers=["demo", "演示"],
                    required_tools=["greet_topic"],
                    input_schema={"type": "object", "properties": {"question": {"type": "string"}}},
                    output_schema={"type": "string"},
                    decision_logic=[{"if": "信息不足", "return": "need_more_info"}, {"else": "use_tool"}],
                    constraints=["Only answer demo prompts."],
                    failure_modes=[{"case": "missing_tool", "effect": "cannot respond"}],
                    fallback_strategy=[{"when": "missing_tool", "action": "return limitation"}],
                    tool_policy={"audit_logging": True},
                )
            ],
            tool_policy={
                "allowlist": ["calculator", "greet_topic"],
                "skill_tool_overrides": {"demo-skill": ["greet_topic"]},
            },
        )

    def test_generate_from_blueprint_creates_runnable_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = BuilderService(root)
            blueprint = self._build_blueprint()

            result = service.generate_from_blueprint(blueprint)

            self.assertTrue((root / "agent_framework" / "agents" / "demo_agent" / "spec.py").exists())
            self.assertTrue((root / "agent_framework" / "agents" / "demo_agent" / "tools.py").exists())
            self.assertTrue((root / "chat_with_demo_agent_agent.py").exists())
            self.assertTrue(result.validation_messages)

            chat_entry = (root / "chat_with_demo_agent_agent.py").read_text(encoding="utf-8")
            self.assertIn("agent_id=spec.agent_id", chat_entry)
            self.assertIn("user_input=user_input", chat_entry)
            self.assertIn("session_id=session_id", chat_entry)

            generated_spec = (
                root / "agent_framework" / "agents" / "demo_agent" / "spec.py"
            ).read_text(encoding="utf-8")
            self.assertIn("requires_active_skill=True", generated_spec)

            exports = (root / "agent_framework" / "agents" / "__init__.py").read_text(encoding="utf-8")
            self.assertIn("create_demo_agent_agent", exports)

    def test_validate_blueprint_rejects_existing_agent_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            existing_dir = root / "agent_framework" / "agents" / "demo_agent"
            existing_dir.mkdir(parents=True)

            service = BuilderService(root)
            issues = service.validate_blueprint(self._build_blueprint())

            self.assertTrue(any("已存在" in issue for issue in issues))

    def test_requirements_roundtrip_invalidates_pending_blueprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = BuilderService(Path(temp_dir))
            requirements = self._build_requirements()
            blueprint = self._build_blueprint()

            state = service.store_pending_blueprint({}, blueprint)
            self.assertIsNotNone(service.load_pending_blueprint(state))

            state = service.store_pending_requirements(state, requirements)
            loaded_requirements = service.load_pending_requirements(state)

            self.assertIsNotNone(loaded_requirements)
            assert loaded_requirements is not None
            self.assertEqual(loaded_requirements.agent_id, requirements.agent_id)
            self.assertIsNone(service.load_pending_blueprint(state))
            self.assertFalse(state["builder"]["awaiting_confirmation"])
            self.assertEqual(state["builder"]["stage"], "requirements_collected")

    def test_render_confirmation_prompt_matches_builder_state(self) -> None:
        service = BuilderService(Path.cwd())
        summary = "agent_id: demo_agent"

        ready_prompt = service.render_confirmation_prompt(
            summary=summary,
            finalization_status="ready_to_generate",
            message="已更新待确认 blueprint。",
            awaiting_confirmation=True,
        )
        self.assertIn("确认创建", ready_prompt)
        self.assertIn(summary, ready_prompt)

        draft_prompt = service.render_confirmation_prompt(
            summary=summary,
            finalization_status="need_more_info",
            message="已更新待确认 blueprint。",
            awaiting_confirmation=False,
        )
        self.assertNotIn("确认创建", draft_prompt)
        self.assertIn("还有些信息需要补充或修正", draft_prompt)

    def test_design_blueprint_from_requirements_produces_minimal_runnable_blueprint(self) -> None:
        service = BuilderService(Path.cwd())
        blueprint = service.design_blueprint_from_requirements(self._build_requirements())

        self.assertEqual(blueprint.agent_id, "demo_agent")
        self.assertEqual(blueprint.name, "Demo Agent")
        self.assertEqual(blueprint.role, "Demo Assistant")
        self.assertEqual(blueprint.goal, "帮助用户完成简单演示任务。")
        self.assertTrue(blueprint.skills)
        self.assertTrue(blueprint.tool_plan)

    def test_normalize_blueprint_payload_does_not_fabricate_required_fields(self) -> None:
        service = BuilderService(Path.cwd())
        blueprint = service.normalize_blueprint_payload({"name": "Only Name"})
        issues = service.validate_blueprint(blueprint)

        self.assertEqual(blueprint.role, "")
        self.assertEqual(blueprint.goal, "")
        self.assertFalse(blueprint.skills)
        self.assertIn("role 不能为空。", issues)
        self.assertIn("goal 不能为空。", issues)
        self.assertIn("至少需要一个 skill。", issues)

    def test_refine_blueprint_preserves_existing_fields(self) -> None:
        service = BuilderService(Path.cwd())
        base = self._build_blueprint()
        refined = service.refine_blueprint(
            base,
            {
                "agent_id": base.agent_id,
                "name": base.name,
                "role": base.role,
                "goal": "帮助用户完成改进后的演示任务。",
                "skills": [
                    {
                        "name": "demo-skill",
                        "description": "Handle refined demo prompts.",
                        "body": "Use `greet_topic` for refined demo prompts.",
                        "required_tools": ["greet_topic"],
                        "input_schema": {"type": "object"},
                        "output_schema": {"type": "string"},
                        "decision_logic": [{"else": "use_tool"}],
                        "constraints": ["Keep responses short."],
                        "failure_modes": [{"case": "tool_error", "effect": "cannot answer"}],
                        "fallback_strategy": [{"when": "tool_error", "action": "report limitation"}],
                        "tool_policy": {"audit_logging": True},
                    }
                ],
            },
        )
        self.assertEqual(refined.goal, "帮助用户完成改进后的演示任务。")
        self.assertEqual(refined.workspace_docs.agents_md, base.workspace_docs.agents_md)
        self.assertEqual(refined.skills[0].name, "demo-skill")

    def test_build_tool_plan_returns_structured_payload(self) -> None:
        service = BuilderService(Path.cwd())
        plan = service.build_tool_plan(self._build_blueprint())
        self.assertEqual(plan.reuse_tools, ["calculator"])
        self.assertEqual(plan.new_tools[0].name, "greet_topic")
        self.assertEqual(plan.new_tools[0].risk_level, "low")

    def test_confirmation_input_requires_exact_phrase(self) -> None:
        service = BuilderService(Path.cwd())

        self.assertTrue(service.is_confirmation_input(BUILDER_CONFIRMATION_PHRASE))
        self.assertFalse(service.is_confirmation_input("开始创建"))
        self.assertFalse(service.is_confirmation_input("确认创建 demo_agent"))


if __name__ == "__main__":
    unittest.main()
