"""Workflow 节点实现。"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Callable, Dict, Iterator, List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.utils import message_chunk_to_message

from agent_framework.bootstrap.injector import BootstrapInjector
from agent_framework.bootstrap.models import BootstrapSnapshot
from agent_framework.builders import BUILDER_CONFIRMATION_PHRASE, BUILDER_STATE_KEY, BuilderService
from agent_framework.config.settings import FrameworkSettings
from agent_framework.core.agent import AgentSpec
from agent_framework.core.events import EventBus
from agent_framework.memory.manager import MemoryManager
from agent_framework.skills.registry import SkillRegistry
from agent_framework.skills.router import SkillRouter
from agent_framework.skills.runtime import SkillRuntime
from agent_framework.tools.executor import ToolExecutor
from agent_framework.tools.models import ToolExecutionContext
from agent_framework.tools.policy import ToolPolicy
from agent_framework.workflows.common.state import WorkflowState, WorkflowStreamEvent


class WorkflowNodes:
    """Workflow 使用的 LangGraph 节点集合。"""

    def __init__(
        self,
        *,
        settings: FrameworkSettings,
        agent_spec: AgentSpec,
        memory_manager: MemoryManager,
        skill_registry: SkillRegistry,
        skill_router: SkillRouter,
        skill_runtime: SkillRuntime,
        bootstrap_snapshot: BootstrapSnapshot,
        bootstrap_injector: BootstrapInjector,
        tool_executor: ToolExecutor,
        tool_policy: ToolPolicy,
        llm: BaseChatModel,
        tool_whitelist: List[str] | None = None,
        event_bus: EventBus | None = None,
        intermediate_state_persist: Callable[[str, str, List[str], Dict[str, Any]], None]
        | None = None,
    ) -> None:
        self.settings = settings
        self.agent_spec = agent_spec
        self.memory_manager = memory_manager
        self.skill_registry = skill_registry
        self.skill_router = skill_router
        self.skill_runtime = skill_runtime
        self.bootstrap_snapshot = bootstrap_snapshot
        self.bootstrap_injector = bootstrap_injector
        self.tool_executor = tool_executor
        self.tool_policy = tool_policy
        self.llm = llm
        self.tool_whitelist = tool_whitelist
        self.event_bus = event_bus
        self.intermediate_state_persist = intermediate_state_persist

    def _builder_service(self) -> BuilderService:
        return BuilderService(self.settings.workspace_root)

    def _emit_stream(self, event_type: str, payload: Dict[str, Any]) -> WorkflowStreamEvent:
        return WorkflowStreamEvent(event_type=event_type, payload=payload)

    def _is_builder_agent(self) -> bool:
        return self.agent_spec.agent_id == "builder"

    def _requires_active_skill_gate(self, state: WorkflowState) -> bool:
        return (
            self.agent_spec.requires_active_skill
            and not self._is_builder_agent()
            and not state.get("active_skills", [])
        )

    def _missing_active_skill_message(self) -> str:
        return (
            "抱歉，我暂时无法处理这个请求。请告诉我你想创建什么样的 agent，"
            "我会帮你设计需求和 blueprint。"
        )

    def _builder_state(self, state: WorkflowState) -> Dict[str, Any]:
        raw_state = state.get("working_state", {}).get(BUILDER_STATE_KEY, {})
        return raw_state if isinstance(raw_state, dict) else {}

    def _builder_pending_summary(self, state: WorkflowState) -> str:
        builder_state = self._builder_state(state)
        return str(
            builder_state.get("pending_blueprint_summary")
            or builder_state.get("requirements_summary")
            or ""
        ).strip()

    def _builder_is_awaiting_confirmation(self, state: WorkflowState) -> bool:
        builder_state = self._builder_state(state)
        return (
            bool(builder_state.get("awaiting_confirmation", False))
            and str(builder_state.get("stage", "")) == "awaiting_confirmation"
        )

    def _builder_pending_blueprint_json(self, state: WorkflowState) -> str | None:
        payload = self._builder_state(state).get("pending_blueprint")
        if not isinstance(payload, dict):
            return None
        return json.dumps(payload, ensure_ascii=False)

    def _builder_pending_requirements_json(self, state: WorkflowState) -> str | None:
        payload = self._builder_state(state).get("pending_requirements")
        if not isinstance(payload, dict):
            return None
        return json.dumps(payload, ensure_ascii=False)

    def _builder_protocol_instructions(self, state: WorkflowState) -> str:
        """builder 非确认阶段的运行时协议指令。"""

        stage = str(self._builder_state(state).get("stage", "requirements_collection"))
        if stage == "requirements_collection":
            return (
                "\n\n[Builder Runtime Protocol]\n"
                '你处于 builder 专用状态机中。除非用户精确输入"确认创建"，否则不要写入仓库文件。\n'
                "当前阶段: requirements_collection\n"
                "请用自然语言与用户交流，从对话中理解并提取需求。\n"
                "当你收集到足够信息时，输出一个 JSON 对象来触发需求保存：\n"
                "{\n"
                '  "action": "collect_requirements",\n'
                '  "payload": {\n'
                '    "agent_name": "agent 名称",\n'
                '    "agent_id": "snake_case 标识符",\n'
                '    "role": "角色描述",\n'
                '    "goal": "核心目标",\n'
                '    "required_skills": ["技能1", "技能2"],\n'
                '    "required_tools": ["工具1", "工具2"],\n'
                '    "style_constraints": ["约束1"],\n'
                '    "memory_requirements": ["记忆需求1"],\n'
                '    "workflow_preferences": ["偏好1"]\n'
                "  },\n"
                '  "user_message": "给用户的需求摘要说明"\n'
                "}\n"
                "规则：\n"
                "1. 优先用自然语言与用户对话，理解他们的需求。\n"
                "2. 只有当信息足够时才输出 JSON，否则继续对话收集。\n"
                "3. 用户描述不完整时，针对性地追问最关键的 1-2 个问题。\n"
                "4. 如果信息不足，返回 ask_more_info，并明确指出缺失点。\n"
                '5. 只有 runtime 判定当前阶段为 awaiting_confirmation，用户输入"确认创建"时才会真正生成文件。\n'
            )
        return (
            "\n\n[Builder Runtime Protocol]\n"
            '你处于 builder 专用状态机中。除非用户精确输入"确认创建"，否则不要写入仓库文件。\n'
            f"当前阶段: {stage}\n"
            "回复请输出一个 JSON 对象，结构如下：\n"
            "{\n"
            '  "action": "collect_requirements" | "design_blueprint" | "refine_blueprint" | "finalize_blueprint" | "ask_more_info",\n'
            '  "payload": { ... },\n'
            '  "user_message": "给用户看的中文说明"\n'
            "}\n"
            "规则：\n"
            "1. collect_requirements 的 payload 必须是 requirements 对象，只收集需求，不生成 blueprint。\n"
            "2. design_blueprint 只能基于已收集的 requirements 设计 blueprint。\n"
            "3. refine/finalize 的 payload 必须是 AgentBlueprint 形状，不要省略必要字段。\n"
            "4. 如果信息不足，返回 ask_more_info，并明确指出缺失点。\n"
            '5. 只有 runtime 判定当前阶段为 awaiting_confirmation，用户输入"确认创建"时才会真正生成文件。\n'
        )

    def _extract_json_payload(self, text: str) -> Dict[str, Any] | None:
        """从模型文本中提取 JSON payload。"""

        fence_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        candidates: List[str] = []
        if fence_match:
            candidates.append(fence_match.group(1))

        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, end = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                candidates.append(text[index : index + end])
                break

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _builder_result_message(self, payload: Dict[str, Any]) -> str:
        if payload.get("ok") is False:
            return str(payload.get("message") or payload.get("error") or "builder 执行失败。")

        lines = [str(payload.get("message") or "builder 执行完成。")]
        agent_id = payload.get("agent_id")
        chat_entry = payload.get("chat_entry")
        validation_messages = payload.get("validation_messages") or []
        if agent_id:
            lines.append(f"agent_id: {agent_id}")
        if chat_entry:
            lines.append(f"chat_entry: {chat_entry}")
        if validation_messages:
            lines.append("validation:")
            lines.extend(f"- {item}" for item in validation_messages)
        return "\n".join(lines)

    def _sanitize_builder_response_text(self, state: WorkflowState, text: str) -> str:
        """只在真实待确认状态下允许确认提示通过。"""

        if not self._is_builder_agent():
            return text
        if not text:
            return text

        confirmation_markers = ("确认创建", '请输入"确认创建"', "请输入\"确认创建\"")
        if not any(marker in text for marker in confirmation_markers):
            return text

        builder_state = self._builder_state(state)
        if builder_state.get("pending_blueprint") and builder_state.get("awaiting_confirmation"):
            return text
        return "当前还没有可确认的 blueprint，请先完成需求收集、蓝图设计和校验。"

    def _sanitize_visible_text(
        self,
        text: str,
        *,
        preserve_thinking: bool = False,
    ) -> str:
        """过滤 provider 返回的内部推理标签。

        对于 builder agent，保留思考标签以便用户能看到 LLM 的推理过程，
        这对于 skill-driven 架构的调试和理解非常重要。
        """

        if not text:
            return text
        if not preserve_thinking:
            sanitized = re.sub(
                r"(?is)<(think|analysis|reasoning)>.*?(</\1>|$)",
                "",
                text,
            )
            sanitized = re.sub(r"(?is)</?(think|analysis|reasoning)>", "", sanitized)
            return sanitized
        return text

    def _sanitize_builder_response_text_with_working_state(
        self,
        text: str,
        working_state: Dict[str, Any],
    ) -> str:
        """基于 working_state 判断 builder 响应是否可以暴露确认提示。"""

        if not self._is_builder_agent() or not text:
            return text
        confirmation_markers = ("确认创建", '请输入"确认创建"', "请输入\"确认创建\"")
        if not any(marker in text for marker in confirmation_markers):
            return text

        builder_state = working_state.get(BUILDER_STATE_KEY, {})
        if (
            isinstance(builder_state, dict)
            and builder_state.get("pending_blueprint")
            and builder_state.get("awaiting_confirmation")
        ):
            return text

        if not builder_state.get("pending_blueprint"):
            return "当前还没有可生成的 blueprint，请继续补充需求或等待系统完成设计。"
        return "当前还没有可确认的 blueprint，请先完成需求收集、蓝图设计和校验。"

    def _sanitize_response_text(
        self,
        state: WorkflowState,
        text: str,
        *,
        working_state: Dict[str, Any] | None = None,
    ) -> str:
        """统一过滤内部推理与非法确认提示。

        对于 builder agent，保留思考标签以便用户能看到 LLM 的推理过程。
        """

        preserve_thinking = self._is_builder_agent()
        visible_text = self._sanitize_visible_text(text, preserve_thinking=preserve_thinking)
        effective_state = (
            working_state if working_state is not None else state.get("working_state", {})
        )
        return self._sanitize_builder_response_text_with_working_state(
            visible_text, effective_state
        )

    def _persist_intermediate_builder_state(
        self,
        state: WorkflowState,
        working_state: Dict[str, Any],
    ) -> None:
        """builder 中间状态先落盘，避免流式中断时丢失。"""

        if not self._is_builder_agent() or self.intermediate_state_persist is None:
            return
        self.intermediate_state_persist(
            state["session_id"],
            state.get("summary", ""),
            list(state.get("active_skills", [])),
            working_state,
        )

    def _builder_tool_finishes_turn(self, tool_name: str) -> bool:
        """这些 builder 工具执行后，本轮可以直接结束。"""

        return tool_name in {
            "save_pending_blueprint",
            "refine_agent_blueprint",
            "finalize_blueprint",
            "plan_agent_tools",
            "confirm_and_generate_agent",
        }

    def _emit_builder_event(
        self, event_type: str, state: WorkflowState, payload: Dict[str, Any]
    ) -> None:
        if self.event_bus is None:
            return
        event_payload = {
            "agent_id": self.agent_spec.agent_id,
            "session_id": state["session_id"],
            **payload,
        }
        self.event_bus.emit(event_type, event_payload)

    def _apply_builder_tool_state(
        self,
        state: WorkflowState,
        tool_name: str,
        payload: Dict[str, Any],
        next_working_state: Dict[str, Any],
    ) -> tuple[Dict[str, Any], str]:
        message = str(payload.get("message") or json.dumps(payload, ensure_ascii=False))
        builder_state = payload.get("builder_state")
        if isinstance(builder_state, dict):
            next_working_state[BUILDER_STATE_KEY] = builder_state

        if tool_name in {"save_pending_blueprint", "refine_agent_blueprint"}:
            self._emit_builder_event(
                "builder.blueprint_drafted",
                state,
                {"summary": payload.get("summary", ""), "tool_name": tool_name},
            )
            self._emit_builder_event(
                "builder.confirmation_requested",
                state,
                {"confirmation_phrase": BUILDER_CONFIRMATION_PHRASE},
            )
        elif tool_name == "plan_agent_tools":
            self._emit_builder_event(
                "builder.tool_plan_updated",
                state,
                {"tool_plan": payload.get("tool_plan", {})},
            )
        elif tool_name == "finalize_blueprint":
            finalization = payload.get("finalization", {})
            self._emit_builder_event(
                "builder.finalization_updated",
                state,
                {"status": finalization.get("status"), "issues": finalization.get("issues", [])},
            )

        builder_state = payload.get("builder_state")
        if isinstance(builder_state, dict):
            summary = str(builder_state.get("pending_blueprint_summary", "")).strip()
            finalization_status = str(builder_state.get("finalization_status", "draft"))
            awaiting_confirmation = bool(builder_state.get("awaiting_confirmation", False))
            message = self._builder_service().render_confirmation_prompt(
                summary=summary,
                finalization_status=finalization_status,
                message=message,
                awaiting_confirmation=awaiting_confirmation,
            )
            self._persist_intermediate_builder_state(state, next_working_state)

        return next_working_state, self._sanitize_response_text(
            state, message, working_state=next_working_state
        )

    def _apply_builder_runtime_action(
        self,
        state: WorkflowState,
        action: str,
        payload: Dict[str, Any],
        user_message: str,
    ) -> Dict[str, Any]:
        """在 runtime 层执行 builder 状态机动作。"""

        service = self._builder_service()
        next_working_state = dict(state.get("working_state", {}))
        existing_requirements = service.load_pending_requirements(next_working_state)
        existing_blueprint = service.load_pending_blueprint(next_working_state)

        if action == "ask_more_info":
            visible_message = (
                user_message or "请继续告诉我你想要什么样的 agent，比如它的角色、目标、需要的技能等。"
            )
            return {
                "messages": [
                    AIMessage(
                        content=self._sanitize_response_text(
                            state,
                            visible_message,
                            working_state=next_working_state,
                        )
                    )
                ],
                "stop_after_tools": False,
            }

        if action == "collect_requirements":
            normalized_requirements = service.normalize_requirements_payload(
                payload, existing_requirements
            )
            next_working_state = service.store_pending_requirements(
                next_working_state, normalized_requirements
            )
            issues = service.validate_requirements(normalized_requirements)
            summary = str(
                next_working_state.get(BUILDER_STATE_KEY, {}).get("requirements_summary", "")
            ).strip()

            if issues:
                message = user_message or "需求已记录，但还需要补充一些关键信息。"
                visible_message = (
                    f"{message}\n\n{summary}\n\n请告诉我以下信息：\n"
                    + "\n".join(f"- {issue}" for issue in issues)
                )
                self._persist_intermediate_builder_state(state, next_working_state)
                return {
                    "messages": [
                        AIMessage(
                            content=self._sanitize_response_text(
                                state,
                                visible_message,
                                working_state=next_working_state,
                            )
                        )
                    ],
                    "working_state": next_working_state,
                    "stop_after_tools": False,
                }

            visible_message = (
                user_message
                or f"需求已记录！以下是已收集的信息：\n\n{summary}\n\n"
                '如果信息完整，我会开始设计 blueprint。你也可以告诉我需要修改的地方。'
            )
            self._persist_intermediate_builder_state(state, next_working_state)
            return {
                "messages": [
                    AIMessage(
                        content=self._sanitize_response_text(
                            state,
                            visible_message,
                            working_state=next_working_state,
                        )
                    )
                ],
                "working_state": next_working_state,
                "stop_after_tools": False,
            }

        if action == "design_blueprint":
            if {"agent_id", "name", "goal", "skills", "tool_plan"}.intersection(payload.keys()):
                normalized = service.normalize_blueprint_payload(payload, existing_blueprint)
            elif payload:
                normalized = service.design_blueprint_from_requirements(payload, existing_blueprint)
            elif existing_requirements is not None:
                normalized = service.design_blueprint_from_requirements(
                    existing_requirements.model_dump(mode="json"),
                    existing_blueprint,
                )
            else:
                return self._apply_builder_runtime_action(
                    state,
                    "ask_more_info",
                    {},
                    user_message or "当前还没有可用的 requirements，请先完成需求收集。",
                )
            next_working_state = service.store_pending_blueprint(next_working_state, normalized)
            finalization = service.finalize_blueprint(normalized)
            builder_state = next_working_state.get(BUILDER_STATE_KEY, {})
            visible_message = service.render_confirmation_prompt(
                summary=str(builder_state.get("pending_blueprint_summary", "")),
                finalization_status=str(
                    builder_state.get("finalization_status", finalization["status"])
                ),
                message=user_message or "已根据当前需求生成 blueprint 草稿。",
                awaiting_confirmation=bool(builder_state.get("awaiting_confirmation", False)),
            )
            self._emit_builder_event(
                "builder.blueprint_drafted",
                state,
                {"status": finalization["status"], "action": action},
            )
            if bool(builder_state.get("awaiting_confirmation", False)):
                self._emit_builder_event(
                    "builder.confirmation_requested",
                    state,
                    {"confirmation_phrase": BUILDER_CONFIRMATION_PHRASE},
                )
            self._persist_intermediate_builder_state(state, next_working_state)
            return {
                "messages": [
                    AIMessage(
                        content=self._sanitize_response_text(
                            state,
                            visible_message,
                            working_state=next_working_state,
                        )
                    )
                ],
                "working_state": next_working_state,
                "stop_after_tools": False,
            }

        if action in {"refine_blueprint", "finalize_blueprint"}:
            if existing_blueprint is None and not payload:
                return self._apply_builder_runtime_action(
                    state,
                    "ask_more_info",
                    {},
                    user_message
                    or "当前还没有待修改的 blueprint，请先完成需求收集和 blueprint 设计。",
                )

            normalized = service.normalize_blueprint_payload(payload, existing_blueprint)
            if action == "refine_blueprint" and existing_blueprint is not None:
                normalized = service.refine_blueprint(existing_blueprint, normalized)

            next_working_state = service.store_pending_blueprint(next_working_state, normalized)
            finalization = service.finalize_blueprint(normalized)
            builder_state = next_working_state.get(BUILDER_STATE_KEY, {})
            visible_message = service.render_confirmation_prompt(
                summary=str(builder_state.get("pending_blueprint_summary", "")),
                finalization_status=str(
                    builder_state.get("finalization_status", finalization["status"])
                ),
                message=user_message or str(finalization["message"]),
                awaiting_confirmation=bool(builder_state.get("awaiting_confirmation", False)),
            )
            self._emit_builder_event(
                "builder.blueprint_drafted"
                if action != "finalize_blueprint"
                else "builder.finalization_updated",
                state,
                {"status": finalization["status"], "action": action},
            )
            if bool(builder_state.get("awaiting_confirmation", False)):
                self._emit_builder_event(
                    "builder.confirmation_requested",
                    state,
                    {"confirmation_phrase": BUILDER_CONFIRMATION_PHRASE},
                )
            self._persist_intermediate_builder_state(state, next_working_state)
            return {
                "messages": [
                    AIMessage(
                        content=self._sanitize_response_text(
                            state,
                            visible_message,
                            working_state=next_working_state,
                        )
                    )
                ],
                "working_state": next_working_state,
                "stop_after_tools": False,
            }

        fallback_message = (
            user_message
            or "builder 无法识别当前动作，请改为收集需求、设计蓝图、修订蓝图或继续补充信息。"
        )
        return {
            "messages": [
                AIMessage(
                    content=self._sanitize_response_text(
                        state,
                        fallback_message,
                        working_state=next_working_state,
                    )
                )
            ],
            "stop_after_tools": False,
        }

    def _extract_requirements_from_natural_language(
        self, state: WorkflowState, model_text: str
    ) -> Dict[str, Any] | None:
        """从 LLM 的自然语言输出中提取结构化 requirements。"""

        user_input = str(state.get("user_input", ""))
        extraction_prompt = (
            "你是一个需求分析助手。请从以下对话内容中提取创建 agent 所需的结构化信息。\n"
            "用户原始输入和 LLM 回复如下：\n\n"
            f"用户输入: {user_input}\n"
            f"LLM 回复: {model_text}\n\n"
            "请提取以下字段（如果信息不足，对应字段留空字符串或空列表）：\n"
            "- agent_name: agent 的名称\n"
            "- agent_id: agent 的标识符（snake_case）\n"
            "- role: agent 的角色描述\n"
            "- goal: agent 的核心目标\n"
            "- required_skills: 需要的技能列表\n"
            "- required_tools: 需要的工具列表\n"
            "- style_constraints: 风格约束列表\n"
            "- memory_requirements: 记忆需求列表\n"
            "- workflow_preferences: 工作流偏好列表\n\n"
            "只输出一个 JSON 对象，不要输出其他内容。"
        )

        try:
            response = self.llm.invoke([SystemMessage(content=extraction_prompt)])
            response_text = response.content if hasattr(response, "content") else str(response)
            parsed = self._extract_json_payload(response_text)
            if parsed and isinstance(parsed, dict) and any(
                parsed.get(k) for k in ["agent_name", "role", "goal"]
            ):
                return parsed
        except Exception:
            pass
        return None

    def _handle_builder_runtime_turn(self, state: WorkflowState, model_text: str) -> Dict[str, Any]:
        """处理 builder 的 JSON envelope。

        在 skill-driven 架构下，LLM 必须输出结构化的 JSON envelope。
        如果输出非 JSON 格式，说明当前激活的 skill 没有正确引导 LLM 输出。
        """

        parsed = self._extract_json_payload(model_text)
        if parsed is None:
            builder_state = self._builder_state(state)
            stage = builder_state.get("stage", "requirements_collection")
            if stage == "requirements_collection":
                extracted = self._extract_requirements_from_natural_language(state, model_text)
                if extracted:
                    return self._apply_builder_runtime_action(
                        state, "collect_requirements", extracted, ""
                    )
                hint = "请按照 skill 协议输出 JSON 格式的 requirements 对象，包含 action、payload 和 user_message 字段。"
            elif stage == "requirements_collected":
                hint = "请调用 design-agent-blueprint skill，输出 JSON 格式的 blueprint 设计。"
            else:
                hint = "当前 stage 不支持非结构化输出，请按 skill 协议输出 JSON。"
            return self._apply_builder_runtime_action(
                state,
                "ask_more_info",
                {},
                hint,
            )

        action = str(parsed.get("action") or "").strip()
        payload = parsed.get("payload")
        user_message = str(parsed.get("user_message") or "").strip()

        if action and isinstance(payload, dict):
            return self._apply_builder_runtime_action(state, action, payload, user_message)
        if {"agent_name", "required_skills", "required_tools", "workflow_preferences"}.intersection(
            parsed.keys()
        ):
            return self._apply_builder_runtime_action(
                state, "collect_requirements", parsed, user_message
            )
        if {"agent_id", "name", "goal", "skills", "tool_plan"}.intersection(parsed.keys()):
            fallback_action = (
                "refine_blueprint"
                if self._builder_state(state).get("pending_blueprint")
                else "finalize_blueprint"
            )
            return self._apply_builder_runtime_action(state, fallback_action, parsed, user_message)
        return self._apply_builder_runtime_action(
            state,
            "ask_more_info",
            {},
            user_message
            or self._sanitize_visible_text(model_text, preserve_thinking=True)
            or "当前信息还不足，请继续补充关键需求。",
        )

    def _handle_builder_confirmation(self, state: WorkflowState) -> Dict[str, Any] | None:
        if not self._is_builder_agent():
            return None

        service = self._builder_service()
        if not service.is_confirmation_input(state["user_input"]):
            return None

        if not self._builder_is_awaiting_confirmation(state):
            self._emit_builder_event(
                "builder.confirmation_rejected", state, {"reason": "no pending blueprint"}
            )
            return {
                "messages": [
                    AIMessage(
                        content="还没有可以确认的 blueprint。请先告诉我你想创建什么样的 agent，我会帮你收集需求并设计 blueprint。"
                    )
                ]
            }

        pending_blueprint = self._builder_pending_blueprint_json(state)
        if pending_blueprint is None:
            self._emit_builder_event(
                "builder.confirmation_rejected",
                state,
                {"reason": "missing pending blueprint"},
            )
            return {
                "messages": [
                    AIMessage(
                        content="还没有可以确认的 blueprint。请先告诉我你想创建什么样的 agent，我会帮你收集需求并设计 blueprint。"
                    )
                ]
            }

        context = ToolExecutionContext(
            agent_id=self.agent_spec.agent_id,
            session_id=state["session_id"],
            active_skills=[],
            tool_whitelist=self.tool_whitelist,
            requires_active_skill=False,
        )
        result = self.tool_executor.execute(
            "confirm_and_generate_agent",
            {"blueprint_json": pending_blueprint, "user_input": state["user_input"]},
            context,
            self.tool_policy,
        )
        if not result.ok:
            self._emit_builder_event(
                "builder.confirmation_rejected",
                state,
                {"reason": result.error or "unknown error"},
            )
            return {"messages": [AIMessage(content=f"创建失败：{result.error or '未知错误'}")]}

        payload = json.loads(str(result.output))
        next_working_state = dict(state.get("working_state", {}))
        builder_state = payload.get("builder_state")
        if isinstance(builder_state, dict):
            next_working_state[BUILDER_STATE_KEY] = builder_state

        self._emit_builder_event(
            "builder.confirmation_accepted",
            state,
            {"agent_id_created": payload.get("agent_id")},
        )
        self._emit_builder_event(
            "builder.build_completed" if payload.get("ok") else "builder.build_failed",
            state,
            {"target_agent_id": payload.get("agent_id"), "error": payload.get("error")},
        )
        self._persist_intermediate_builder_state(state, next_working_state)
        return {
            "messages": [
                AIMessage(
                    content=self._sanitize_response_text(
                        state,
                        self._builder_result_message(payload),
                        working_state=next_working_state,
                    )
                )
            ],
            "working_state": next_working_state,
        }

    def _message_text(self, message: BaseMessage | AIMessageChunk) -> str:
        content = getattr(message, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                    continue
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
            return "".join(text_parts)
        return str(content)

    def _stream_text_delta(self, current_text: str, last_emitted_text: str) -> str:
        """把 provider 返回的累计文本规整成真实增量。"""

        if not current_text:
            return ""
        if current_text.startswith(last_emitted_text):
            return current_text[len(last_emitted_text) :]
        if current_text == last_emitted_text:
            return ""
        return current_text

    def _normalize_tool_call_chunks(
        self,
        tool_call_chunks: List[dict[str, Any]],
        observed_tool_calls: Dict[int, Dict[str, str]],
    ) -> tuple[List[dict[str, Any]], Dict[int, Dict[str, str]]]:
        """把 cumulative tool_call_chunks 规整成真实增量片段。"""

        next_observed = {index: dict(values) for index, values in observed_tool_calls.items()}
        normalized_chunks: List[dict[str, Any]] = []

        for raw_chunk in tool_call_chunks:
            chunk = dict(raw_chunk)
            index = chunk.get("index")
            if not isinstance(index, int):
                normalized_chunks.append(chunk)
                continue

            previous = next_observed.get(index, {})
            normalized: dict[str, Any] = {"index": index}
            has_delta = False

            for field_name in ("name", "id", "args"):
                current_value = chunk.get(field_name)
                if not isinstance(current_value, str) or current_value == "":
                    continue

                previous_value = previous.get(field_name, "")
                if previous_value and current_value == previous_value:
                    delta_value = ""
                    full_value = current_value
                elif previous_value and current_value.startswith(previous_value):
                    delta_value = current_value[len(previous_value) :]
                    full_value = current_value
                elif previous_value:
                    delta_value = current_value
                    full_value = previous_value + current_value
                else:
                    delta_value = current_value
                    full_value = current_value

                previous[field_name] = full_value
                if delta_value:
                    normalized[field_name] = delta_value
                    has_delta = True

            if previous:
                next_observed[index] = previous
            if has_delta:
                normalized_chunks.append(normalized)

        return normalized_chunks, next_observed

    def _normalize_stream_chunk(
        self,
        chunk: AIMessageChunk,
        observed_text: str,
        observed_tool_calls: Dict[int, Dict[str, str]],
    ) -> tuple[AIMessageChunk, str, str, Dict[int, Dict[str, str]]]:
        """把 provider 的 chunk 规整成真实 delta chunk。"""

        normalized_tool_call_chunks, next_observed_tool_calls = self._normalize_tool_call_chunks(
            list(chunk.tool_call_chunks),
            observed_tool_calls,
        )

        chunk_text = self._message_text(chunk)
        if chunk_text.startswith(observed_text):
            current_full_text = chunk_text
            raw_delta_text = chunk_text[len(observed_text) :]
        elif not chunk_text:
            current_full_text = observed_text
            raw_delta_text = ""
        else:
            current_full_text = observed_text + chunk_text
            raw_delta_text = chunk_text
        previous_visible_text = self._sanitize_visible_text(observed_text)
        current_visible_text = self._sanitize_visible_text(current_full_text)
        delta_text = self._stream_text_delta(current_visible_text, previous_visible_text)

        normalized_content: Any = chunk.content
        if isinstance(chunk.content, str):
            normalized_content = raw_delta_text
        elif not current_visible_text and chunk_text:
            normalized_content = ""

        normalized_chunk = chunk.model_copy(
            update={
                "content": normalized_content,
                "tool_call_chunks": normalized_tool_call_chunks,
            }
        )
        return normalized_chunk, current_full_text, delta_text, next_observed_tool_calls

    def _build_llm_messages(
        self, state: WorkflowState
    ) -> tuple[List[BaseMessage], ToolExecutionContext]:
        active_skills = [
            skill
            for skill in self.skill_registry.enabled()
            if skill.name in state.get("active_skills", [])
        ]
        sections = self.bootstrap_injector.build_prompt_sections(
            snapshot=self.bootstrap_snapshot,
            active_skills=active_skills,
            memory_hits=state.get("memory_hits", []),
            summary=state.get("summary", ""),
            mode="main",
            task_brief=state.get("task_brief") or None,
        )
        system_prompt = self.bootstrap_injector.render_system_prompt(sections)
        if self._is_builder_agent():
            pending_summary = self._builder_pending_summary(state)
            system_prompt += self._builder_protocol_instructions(state)
            if pending_summary:
                system_prompt += (
                    "\n\n[Builder Session State]\n"
                    f'当前会话保存了 builder 中间状态。只有 runtime 判定允许确认，且用户精确输入"{BUILDER_CONFIRMATION_PHRASE}"时，才允许真正写入文件。\n'
                    "如果用户修改需求，你必须输出新的 requirements 或 blueprint，并要求重新经过校验与确认。\n"
                    f"当前摘要：\n{pending_summary}"
                )

        context = ToolExecutionContext(
            agent_id=self.agent_spec.agent_id,
            session_id=state["session_id"],
            active_skills=list(state.get("active_skills", [])),
            tool_whitelist=self.tool_whitelist,
            requires_active_skill=self.agent_spec.requires_active_skill,
        )
        formatted_messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
        for message in state.get("messages", []):
            if isinstance(message, SystemMessage):
                formatted_messages[0].content += f"\n\nAdditional context: {message.content}"
                continue
            if isinstance(message, ToolMessage):
                content_str = str(message.content)
                if content_str.lower().endswith((".png", ".jpg", ".jpeg")) and os.path.exists(
                    content_str
                ):
                    with open(content_str, "rb") as image_file:
                        encoded = base64.b64encode(image_file.read()).decode("utf-8")
                    ext = os.path.splitext(content_str)[1].lower().lstrip(".")
                    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
                        ext, "image/png"
                    )
                    formatted_messages.append(
                        ToolMessage(
                            content=[
                                {
                                    "type": "text",
                                    "text": f"Tool execution result image: {content_str}",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                                },
                            ],
                            tool_call_id=message.tool_call_id,
                            name=message.name,
                        )
                    )
                    continue
            formatted_messages.append(message)
        return formatted_messages, context

    def retrieve_context(self, state: WorkflowState) -> Dict[str, Any]:
        """从长期记忆中检索与当前输入相关的上下文。"""

        memory_hits = self.memory_manager.retrieve(
            state["user_input"],
            self.agent_spec.memory_namespaces,
        )

        # 检索相关经验
        experience_hits = []
        if hasattr(self.memory_manager, "long_term_store"):
            try:
                from agent_framework.memory.reuse.retriever import ExperienceReuser

                reuser = ExperienceReuser(self.memory_manager.long_term_store)
                experiences = reuser.retrieve_experiences(
                    state["user_input"],
                    ["procedures", "episodes", "user_preferences"],
                    top_k=5,
                )
                if experiences:
                    experience_hits = reuser.format_experiences_for_prompt(experiences)
                    # 更新使用统计
                    reuser.update_usage_stats(experiences)
            except Exception:
                pass

        # 合并记忆命中
        all_hits = memory_hits.copy()
        if experience_hits:
            all_hits.append(experience_hits)

        if all_hits:
            self._emit_builder_event("memory.hit", state, {"hits": all_hits})
        return {"memory_hits": all_hits}

    def route_skills(self, state: WorkflowState) -> Dict[str, Any]:
        """选择当前轮需要激活的 skill。

        对于 builder agent，会根据 builder_state.stage 强制激活对应的 skill，
        确保 workflow 严格按照 requirements -> blueprint -> confirm 的顺序执行。
        """

        candidates = self.skill_registry.enabled()
        routing_context: Dict[str, Any] = {}
        if self._is_builder_agent():
            builder_state = self._builder_state(state)
            routing_context["builder_state"] = builder_state
        routed = self.skill_router.route(state["user_input"], candidates, routing_context)

        # 基于经验提升技能路由分数
        if hasattr(self.memory_manager, "long_term_store"):
            try:
                from agent_framework.memory.reuse.retriever import ExperienceReuser

                reuser = ExperienceReuser(self.memory_manager.long_term_store)
                routed = reuser.boost_skill_routing(routed, state["user_input"])
            except Exception:
                pass

        activated = self.skill_runtime.activate(routed)
        if self.event_bus is not None:
            self.event_bus.emit(
                "skill.routed",
                {
                    "agent_id": self.agent_spec.agent_id,
                    "session_id": state["session_id"],
                    "skills": [skill.name for skill in activated],
                },
            )
        return {"active_skills": [skill.name for skill in activated]}

    def _handle_builder_auto_transition(self, state: WorkflowState) -> Dict[str, Any] | None:
        """处理 builder 的自动阶段转换（如用户说"继续"时自动进入 blueprint 设计）。"""

        if not self._is_builder_agent():
            return None

        user_input = str(state.get("user_input", "")).strip().lower()
        builder_state = self._builder_state(state)
        stage = builder_state.get("stage", "requirements_collection")

        auto_design_triggers = {"继续", "开始设计", "下一步", "go", "next"}
        if stage == "requirements_collected" and user_input in auto_design_triggers:
            existing_requirements = self._builder_service().load_pending_requirements(
                state.get("working_state", {})
            )
            if existing_requirements is not None:
                return self._apply_builder_runtime_action(
                    state,
                    "design_blueprint",
                    existing_requirements.model_dump(mode="json"),
                    "",
                )
        return None

    def agent(self, state: WorkflowState) -> Dict[str, Any]:
        """组装 prompt、绑定工具并调用 LLM。"""

        auto_transition = self._handle_builder_auto_transition(state)
        if auto_transition is not None:
            return auto_transition

        builder_confirmation = self._handle_builder_confirmation(state)
        if builder_confirmation is not None:
            return builder_confirmation
        if self._requires_active_skill_gate(state):
            return {
                "messages": [AIMessage(content=self._missing_active_skill_message())],
                "stop_after_tools": False,
            }
        formatted_messages, context = self._build_llm_messages(state)
        if self._is_builder_agent():
            response = self.llm.invoke(formatted_messages)
            if isinstance(response, AIMessage) and response.tool_calls:
                sanitized_text = self._sanitize_response_text(state, self._message_text(response))
                if sanitized_text != self._message_text(response):
                    response = response.model_copy(update={"content": sanitized_text})
                return {"messages": [response], "stop_after_tools": False}
            return self._handle_builder_runtime_turn(state, self._message_text(response))
        active_skill_names = list(state.get("active_skills", []))
        visible_tools, visible_tool_names = self.tool_executor.build_filtered_langchain_tools(
            context=context, policy=self.tool_policy, active_skills=active_skill_names
        )
        llm_with_tools = self.llm.bind_tools(visible_tools)
        response = llm_with_tools.invoke(formatted_messages)
        sanitized_text = self._sanitize_response_text(state, self._message_text(response))
        if sanitized_text != self._message_text(response):
            response = response.model_copy(update={"content": sanitized_text})
        return {"messages": [response], "stop_after_tools": False, "visible_tool_names": visible_tool_names}

    def agent_stream(self, state: WorkflowState) -> Iterator[WorkflowStreamEvent]:
        """流式执行 agent 节点，并在结束时回填完整 AIMessage。"""

        auto_transition = self._handle_builder_auto_transition(state)
        if auto_transition is not None:
            transition_text = ""
            for message in auto_transition.get("messages", []):
                if isinstance(message, AIMessage):
                    transition_text = self._sanitize_visible_text(self._message_text(message))
                    if transition_text:
                        yield self._emit_stream("text_delta", {"text": transition_text})
            yield self._emit_stream("agent_updates", {"updates": auto_transition})
            return

        builder_confirmation = self._handle_builder_confirmation(state)
        if builder_confirmation is not None:
            confirmation_text = ""
            for message in builder_confirmation.get("messages", []):
                if isinstance(message, AIMessage):
                    confirmation_text = self._sanitize_visible_text(self._message_text(message))
                    if confirmation_text:
                        yield self._emit_stream("text_delta", {"text": confirmation_text})
            yield self._emit_stream("agent_updates", {"updates": builder_confirmation})
            return

        if self._requires_active_skill_gate(state):
            message = self._missing_active_skill_message()
            yield self._emit_stream("text_delta", {"text": message})
            yield self._emit_stream(
                "agent_updates",
                {"updates": {"messages": [AIMessage(content=message)], "stop_after_tools": False}},
            )
            return

        formatted_messages, context = self._build_llm_messages(state)
        if self._is_builder_agent():
            response: AIMessage | None = None
            observed_text = ""
            stream_callable = getattr(self.llm, "stream", None)
            if callable(stream_callable):
                aggregated_chunk: AIMessageChunk | None = None
                observed_tool_calls: Dict[int, Dict[str, str]] = {}
                for chunk in stream_callable(formatted_messages):
                    if isinstance(chunk, AIMessageChunk):
                        normalized_chunk, observed_text, _, observed_tool_calls = (
                            self._normalize_stream_chunk(
                                chunk,
                                observed_text,
                                observed_tool_calls,
                            )
                        )
                        aggregated_chunk = (
                            normalized_chunk
                            if aggregated_chunk is None
                            else aggregated_chunk + normalized_chunk
                        )
                        continue
                    if isinstance(chunk, AIMessage):
                        response = chunk
                        observed_text = self._message_text(chunk)
                if response is None and aggregated_chunk is not None:
                    response = message_chunk_to_message(aggregated_chunk)

            if response is None:
                response = self.llm.invoke(formatted_messages)

            if isinstance(response, AIMessage) and response.tool_calls:
                yield self._emit_stream(
                    "agent_updates",
                    {"updates": {"messages": [response], "stop_after_tools": False}},
                )
                return

            updates = self._handle_builder_runtime_turn(state, self._message_text(response))
            for message in updates.get("messages", []):
                if isinstance(message, AIMessage):
                    visible_text = self._sanitize_visible_text(self._message_text(message))
                    if visible_text:
                        yield self._emit_stream("text_delta", {"text": visible_text})
            yield self._emit_stream("agent_updates", {"updates": updates})
            return

        active_skill_names = list(state.get("active_skills", []))
        visible_tools, visible_tool_names = self.tool_executor.build_filtered_langchain_tools(
            context=context, policy=self.tool_policy, active_skills=active_skill_names
        )
        llm_with_tools = self.llm.bind_tools(visible_tools)

        response: AIMessage | None = None
        observed_text = ""
        observed_tool_calls: Dict[int, Dict[str, str]] = {}
        stream_callable = getattr(llm_with_tools, "stream", None)
        if callable(stream_callable):
            aggregated_chunk: AIMessageChunk | None = None
            for chunk in stream_callable(formatted_messages):
                if isinstance(chunk, AIMessageChunk):
                    normalized_chunk, observed_text, text_delta, observed_tool_calls = (
                        self._normalize_stream_chunk(
                            chunk,
                            observed_text,
                            observed_tool_calls,
                        )
                    )
                    aggregated_chunk = (
                        normalized_chunk
                        if aggregated_chunk is None
                        else aggregated_chunk + normalized_chunk
                    )
                    if text_delta:
                        yield self._emit_stream("text_delta", {"text": text_delta})
                    continue
                if isinstance(chunk, AIMessage):
                    response = chunk
                    current_text = self._message_text(chunk)
                    text_delta = self._stream_text_delta(
                        self._sanitize_visible_text(current_text),
                        self._sanitize_visible_text(observed_text),
                    )
                    if text_delta:
                        yield self._emit_stream("text_delta", {"text": text_delta})
                    observed_text = current_text
            if response is None and aggregated_chunk is not None:
                response = message_chunk_to_message(aggregated_chunk)

        if response is None:
            response = llm_with_tools.invoke(formatted_messages)
            current_text = self._message_text(response)
            text_delta = self._stream_text_delta(
                self._sanitize_visible_text(current_text),
                self._sanitize_visible_text(observed_text),
            )
            if text_delta:
                yield self._emit_stream("text_delta", {"text": text_delta})

        sanitized_text = self._sanitize_response_text(state, self._message_text(response))
        if sanitized_text != self._message_text(response):
            response = response.model_copy(update={"content": sanitized_text})

        yield self._emit_stream(
            "agent_updates", {"updates": {"messages": [response], "stop_after_tools": False, "visible_tool_names": visible_tool_names}}
        )

    def tools(self, state: WorkflowState) -> Dict[str, Any]:
        """执行模型刚刚发出的 tool_calls（带可见性验证）。"""
        from agent_framework.tools.validated_tool_node import validate_tool_calls
        return validate_tool_calls(state, self._tools_impl)

    def _tools_impl(self, state: WorkflowState) -> Dict[str, Any]:
        """实际执行 tool_calls。"""

        messages = state.get("messages", [])
        if not messages:
            return {}

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {}

        context = ToolExecutionContext(
            agent_id=self.agent_spec.agent_id,
            session_id=state["session_id"],
            active_skills=list(state.get("active_skills", [])),
            tool_whitelist=self.tool_whitelist,
            requires_active_skill=self.agent_spec.requires_active_skill,
        )
        tool_messages: List[ToolMessage] = []
        assistant_messages: List[AIMessage] = []
        next_working_state = dict(state.get("working_state", {}))
        stop_after_tools = False

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            payload = tool_call.get("args", {})
            result = self.tool_executor.execute(tool_name, payload, context, self.tool_policy)
            if self.event_bus is not None:
                self.event_bus.emit(
                    "tool.called",
                    {
                        "agent_id": self.agent_spec.agent_id,
                        "session_id": state["session_id"],
                        "tool": tool_name,
                        "ok": result.ok,
                        "error": result.error,
                    },
                )

            content = result.output if result.ok else f"Tool error: {result.error}"
            if result.ok and self._is_builder_agent():
                parsed: Dict[str, Any] | None = None
                try:
                    parsed_candidate = json.loads(str(result.output))
                    if isinstance(parsed_candidate, dict):
                        parsed = parsed_candidate
                except json.JSONDecodeError:
                    parsed = None
                if parsed is not None and isinstance(parsed.get("builder_state"), dict):
                    next_working_state, content = self._apply_builder_tool_state(
                        state,
                        tool_name,
                        parsed,
                        next_working_state,
                    )
                    if self._builder_tool_finishes_turn(tool_name):
                        assistant_messages.append(
                            AIMessage(
                                content=self._sanitize_response_text(
                                    state,
                                    str(content),
                                    working_state=next_working_state,
                                )
                            )
                        )
                        stop_after_tools = True

            tool_messages.append(
                ToolMessage(
                    content=content,
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
            )

        updates: Dict[str, Any] = {
            "messages": tool_messages + assistant_messages,
            "stop_after_tools": stop_after_tools,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }
        if next_working_state != state.get("working_state", {}):
            updates["working_state"] = next_working_state
        return updates

    def tools_stream(self, state: WorkflowState) -> Iterator[WorkflowStreamEvent]:
        """执行 tool_calls，并额外产出工具阶段事件。"""

        messages = state.get("messages", [])
        if not messages:
            return

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return

        # 可见性验证：过滤掉非法工具调用
        visible_tools = set(state.get("visible_tool_names", []))
        if visible_tools:
            invalid = [tc for tc in last_message.tool_calls if tc["name"] not in visible_tools]
            if invalid:
                error_messages = [
                    ToolMessage(
                        content=f"Error: Tool '{tc['name']}' is not available in the current context.",
                        tool_call_id=tc["id"],
                        name=tc["name"],
                    )
                    for tc in invalid
                ]
                yield self._emit_stream("tool_updates", {"updates": {"messages": error_messages}})
                # 如果全是非法调用，直接返回
                valid = [tc for tc in last_message.tool_calls if tc["name"] in visible_tools]
                if not valid:
                    return
                # 混合场景：替换 AIMessage 为过滤后的版本
                filtered_msg = AIMessage(
                    content=last_message.content,
                    additional_kwargs=last_message.additional_kwargs,
                    tool_calls=valid,
                    id=last_message.id,
                )
                for i, msg in enumerate(messages):
                    if msg is last_message:
                        messages = list(messages)
                        messages[i] = filtered_msg
                        last_message = filtered_msg
                        break

        context = ToolExecutionContext(
            agent_id=self.agent_spec.agent_id,
            session_id=state["session_id"],
            active_skills=list(state.get("active_skills", [])),
            tool_whitelist=self.tool_whitelist,
            requires_active_skill=self.agent_spec.requires_active_skill,
        )
        tool_messages: List[ToolMessage] = []
        assistant_messages: List[AIMessage] = []
        next_working_state = dict(state.get("working_state", {}))
        stop_after_tools = False

        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            payload = tool_call.get("args", {})
            yield self._emit_stream(
                "tool_call_started", {"tool_name": tool_name, "payload": payload}
            )
            result = self.tool_executor.execute(tool_name, payload, context, self.tool_policy)
            if self.event_bus is not None:
                self.event_bus.emit(
                    "tool.called",
                    {
                        "agent_id": self.agent_spec.agent_id,
                        "session_id": state["session_id"],
                        "tool": tool_name,
                        "ok": result.ok,
                        "error": result.error,
                    },
                )
            yield self._emit_stream(
                "tool_call_finished",
                {"tool_name": tool_name, "ok": result.ok, "error": result.error},
            )

            content = result.output if result.ok else f"Tool error: {result.error}"
            if result.ok and self._is_builder_agent():
                parsed: Dict[str, Any] | None = None
                try:
                    parsed_candidate = json.loads(str(result.output))
                    if isinstance(parsed_candidate, dict):
                        parsed = parsed_candidate
                except json.JSONDecodeError:
                    parsed = None
                if parsed is not None and isinstance(parsed.get("builder_state"), dict):
                    next_working_state, content = self._apply_builder_tool_state(
                        state,
                        tool_name,
                        parsed,
                        next_working_state,
                    )
                    if self._builder_tool_finishes_turn(tool_name):
                        visible_content = self._sanitize_response_text(
                            state,
                            str(content),
                            working_state=next_working_state,
                        )
                        assistant_messages.append(AIMessage(content=visible_content))
                        if visible_content:
                            yield self._emit_stream("text_delta", {"text": visible_content})
                        stop_after_tools = True

            tool_messages.append(
                ToolMessage(
                    content=content,
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
            )

        updates: Dict[str, Any] = {
            "messages": tool_messages + assistant_messages,
            "stop_after_tools": stop_after_tools,
            "iteration_count": state.get("iteration_count", 0) + 1,
        }
        if next_working_state != state.get("working_state", {}):
            updates["working_state"] = next_working_state
        yield self._emit_stream("tool_updates", {"updates": updates})

    def summarize(self, state: WorkflowState) -> Dict[str, Any]:
        """在消息过长时更新 session summary。"""

        summary = self.memory_manager.compact_if_needed(
            session_id=state["session_id"],
            llm=self.llm,
            messages=state.get("messages", []),
            max_history_messages=self.settings.max_history_messages,
            keep_last=self.settings.summary_keep_last_messages,
        )
        return {"summary": summary}
