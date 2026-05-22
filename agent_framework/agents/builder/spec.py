"""Builder agent 的正式注册入口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from agent_framework.builders import (
    BUILDER_CONFIRMATION_PHRASE,
    AgentBlueprint,
    BuilderService,
)
from agent_framework.config.settings import FrameworkSettings, get_settings
from agent_framework.core.agent import AgentSpec
from agent_framework.tools.adapters.local import build_local_tool_spec
from agent_framework.tools.basic import calculator, current_time
from agent_framework.tools.file_tools import list_directory, read_local_file
from agent_framework.tools.models import ToolSpec
from agent_framework.tools.policy import ToolPolicy


def create_builder_agent(
    llm: BaseChatModel,
    settings: FrameworkSettings | None = None,
) -> Tuple[AgentSpec, List[ToolSpec]]:
    """构造 builder agent 的规格与工具集合。"""

    cfg = settings or get_settings()
    service = BuilderService(cfg.workspace_root)

    def _draft_blueprint(blueprint_json: str) -> AgentBlueprint:
        return service.draft_blueprint(blueprint_json)

    def _state_payload(
        *,
        message: str,
        builder_state: Dict[str, Any],
        ok: bool = True,
        extra: Dict[str, Any] | None = None,
    ) -> str:
        payload: Dict[str, Any] = {"ok": ok, "message": message, "builder_state": builder_state}
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def save_pending_blueprint(blueprint_json: str) -> str:
        """保存待确认 blueprint，并更新 builder 会话态。"""

        blueprint = _draft_blueprint(blueprint_json)
        builder_state = service.store_pending_blueprint({}, blueprint).get("builder", {})
        finalization = service.finalize_blueprint(blueprint)
        message = builder_state.get("last_build_result", {}).get("message", "已保存待确认 blueprint。")
        return _state_payload(
            message=str(message),
            builder_state=builder_state,
            extra={
                "summary": builder_state.get("pending_blueprint_summary", ""),
                "tool_plan": builder_state.get("tool_plan", {}),
                "finalization": finalization,
            },
        )

    @tool
    def load_pending_blueprint(builder_state_json: str) -> str:
        """读取当前 builder 会话中的待确认 blueprint。"""

        working_state = {"builder": json.loads(builder_state_json)}
        blueprint = service.load_pending_blueprint(working_state)
        if blueprint is None:
            return json.dumps({"ok": False, "message": "当前没有待确认的 blueprint。"}, ensure_ascii=False)
        return json.dumps(
            {
                "ok": True,
                "blueprint": blueprint.model_dump(mode="json"),
                "summary": service.summarize_blueprint(blueprint),
            },
            ensure_ascii=False,
        )

    @tool
    def clear_pending_blueprint(builder_state_json: str, reason: str = "") -> str:
        """清空待确认 blueprint。"""

        working_state = {"builder": json.loads(builder_state_json)}
        next_state = service.clear_pending_blueprint(
            working_state,
            {"status": "cleared", "message": reason or "已清空待确认 blueprint。"},
        )
        return _state_payload(
            message=reason or "已清空待确认 blueprint。",
            builder_state=next_state.get("builder", {}),
        )

    @tool
    def refine_agent_blueprint(base_blueprint_json: str, refinement_json: str) -> str:
        """对现有 blueprint 做增量修改，不重建整个对象。"""

        refined = service.refine_blueprint(base_blueprint_json, refinement_json)
        builder_state = service.store_pending_blueprint({}, refined).get("builder", {})
        finalization = service.finalize_blueprint(refined)
        message = "已更新待确认 blueprint，需要重新确认。"
        return _state_payload(
            message=message,
            builder_state=builder_state,
            extra={
                "summary": builder_state.get("pending_blueprint_summary", ""),
                "tool_plan": builder_state.get("tool_plan", {}),
                "finalization": finalization,
                "blueprint": refined.model_dump(mode="json"),
            },
        )

    @tool
    def finalize_blueprint(blueprint_json: str) -> str:
        """检查 blueprint 是否达到可生成状态。"""

        blueprint = _draft_blueprint(blueprint_json)
        builder_state = service.store_pending_blueprint({}, blueprint).get("builder", {})
        finalization = service.finalize_blueprint(blueprint)
        return _state_payload(
            message=str(finalization["message"]),
            builder_state=builder_state,
            extra={"finalization": finalization},
            ok=finalization["status"] == "ready_to_generate",
        )

    @tool
    def plan_agent_tools(blueprint_json: str) -> str:
        """为 blueprint 生成结构化 ToolPlan。"""

        blueprint = _draft_blueprint(blueprint_json)
        builder_state = service.store_pending_blueprint({}, blueprint).get("builder", {})
        tool_plan = service.build_tool_plan(blueprint)
        return _state_payload(
            message="已生成 ToolPlan。",
            builder_state=builder_state,
            extra={"tool_plan": tool_plan.model_dump(mode="json")},
        )

    @tool
    def generate_workspace(blueprint_json: str) -> str:
        """只生成 workspace 文档。"""

        blueprint = _draft_blueprint(blueprint_json)
        files = service.generate_workspace(blueprint)
        return json.dumps(
            {"ok": True, "message": "workspace 文档已生成。", "created_files": [str(path) for path in files]},
            ensure_ascii=False,
        )

    @tool
    def generate_skills(blueprint_json: str) -> str:
        """只生成 skill 包。"""

        blueprint = _draft_blueprint(blueprint_json)
        files = service.generate_skills(blueprint)
        return json.dumps(
            {"ok": True, "message": "skills 已生成。", "created_files": [str(path) for path in files]},
            ensure_ascii=False,
        )

    @tool
    def generate_tools(blueprint_json: str) -> str:
        """只生成本地工具模块。"""

        blueprint = _draft_blueprint(blueprint_json)
        files = service.generate_tools(blueprint)
        return json.dumps(
            {"ok": True, "message": "tools 已生成。", "created_files": [str(path) for path in files]},
            ensure_ascii=False,
        )

    @tool
    def generate_spec(blueprint_json: str) -> str:
        """只生成 spec.py 与 __init__.py。"""

        blueprint = _draft_blueprint(blueprint_json)
        files = service.generate_spec(blueprint)
        return json.dumps(
            {"ok": True, "message": "spec 已生成。", "created_files": [str(path) for path in files]},
            ensure_ascii=False,
        )

    @tool
    def validate_generated_agent(agent_id: str) -> str:
        """校验生成出的 agent 是否可导入。"""

        messages = service.validate_generated_agent(agent_id)
        return json.dumps(
            {"ok": True, "message": "校验已完成。", "validation_messages": messages},
            ensure_ascii=False,
        )

    @tool
    def generate_agent_scaffold(blueprint_json: str) -> str:
        """兼容编排器：顺序生成 workspace、skills、tools、spec 并校验。"""

        blueprint = _draft_blueprint(blueprint_json)
        result = service.generate_agent_scaffold(blueprint)
        return json.dumps(
            {
                "ok": True,
                "message": "agent 脚手架已生成。",
                "agent_id": result.agent_id,
                "created_files": [str(path) for path in result.created_files],
                "validation_messages": result.validation_messages,
                "chat_entry": str(result.chat_entry) if result.chat_entry else None,
            },
            ensure_ascii=False,
        )

    @tool
    def confirm_and_generate_agent(blueprint_json: str, user_input: str) -> str:
        """确认词命中后执行生成。"""

        blueprint = _draft_blueprint(blueprint_json)
        if not service.is_confirmation_input(user_input):
            builder_state = service.store_pending_blueprint({}, blueprint).get("builder", {})
            return _state_payload(
                message=f"请精确输入“{BUILDER_CONFIRMATION_PHRASE}”后再执行写入。",
                builder_state=builder_state,
                ok=False,
            )

        try:
            result = service.generate_from_blueprint(blueprint)
        except Exception as exc:
            failed_state = service.mark_build_failure({}, blueprint, str(exc)).get("builder", {})
            return _state_payload(
                message=f"创建失败：{exc}",
                builder_state=failed_state,
                ok=False,
                extra={"error": str(exc), "agent_id": blueprint.agent_id},
            )

        final_result = service.build_completed_result(result)
        cleared_state = service.clear_pending_blueprint({}, final_result).get("builder", {})
        return _state_payload(
            message=str(final_result["message"]),
            builder_state=cleared_state,
            extra={
                "agent_id": blueprint.agent_id,
                "created_files": final_result["created_files"],
                "validation_messages": final_result["validation_messages"],
                "chat_entry": final_result["chat_entry"],
            },
        )

    workspace_dir = Path(__file__).resolve().parent / "workspace"
    skills_dir = Path(__file__).resolve().parent / "skills"
    spec = AgentSpec(
        agent_id="builder",
        name="Builder Agent",
        workspace_dir=workspace_dir,
        skills_dirs=[skills_dir],
        llm=llm,
        tool_policy=ToolPolicy(
            allowlist=[
                "calculator",
                "current_time",
                "read_local_file",
                "list_directory",
                "save_pending_blueprint",
                "load_pending_blueprint",
                "clear_pending_blueprint",
                "refine_agent_blueprint",
                "finalize_blueprint",
                "plan_agent_tools",
                "generate_workspace",
                "generate_skills",
                "generate_tools",
                "generate_spec",
                "validate_generated_agent",
                "generate_agent_scaffold",
                "confirm_and_generate_agent",
            ],
            skill_tool_overrides={
                "refine-agent-blueprint": ["refine_agent_blueprint", "save_pending_blueprint"],
                "finalize-blueprint": ["finalize_blueprint"],
                "plan-agent-tools": ["plan_agent_tools"],
                "generate-workspace": ["generate_workspace"],
                "generate-skills": ["generate_skills"],
                "generate-tools": ["generate_tools"],
                "generate-spec": ["generate_spec"],
                "generate-agent-scaffold": [
                    "generate_agent_scaffold",
                    "validate_generated_agent",
                    "confirm_and_generate_agent",
                ],
                "validate-generated-agent": ["validate_generated_agent"],
            },
        ),
        memory_namespaces=["semantic", "episodic", "user_memory", "task_memory", "tool_notes", "procedures", "episodes", "user_preferences"],
        workflow_name="builder_agent",
        max_active_skills=4,
    )
    tools = [
        build_local_tool_spec(calculator),
        build_local_tool_spec(current_time),
        build_local_tool_spec(read_local_file),
        build_local_tool_spec(list_directory),
        build_local_tool_spec(save_pending_blueprint),
        build_local_tool_spec(load_pending_blueprint),
        build_local_tool_spec(clear_pending_blueprint, side_effect_level="medium"),
        build_local_tool_spec(refine_agent_blueprint),
        build_local_tool_spec(finalize_blueprint),
        build_local_tool_spec(plan_agent_tools),
        build_local_tool_spec(generate_workspace, side_effect_level="medium"),
        build_local_tool_spec(generate_skills, side_effect_level="medium"),
        build_local_tool_spec(generate_tools, side_effect_level="high"),
        build_local_tool_spec(generate_spec, side_effect_level="medium"),
        build_local_tool_spec(validate_generated_agent),
        build_local_tool_spec(generate_agent_scaffold, side_effect_level="high"),
        build_local_tool_spec(confirm_and_generate_agent, side_effect_level="high"),
    ]
    return spec, tools
