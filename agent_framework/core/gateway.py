"""框架统一入口。

Gateway 负责拼装各子系统，并协调一次完整的 agent run。LangGraph workflow
 只是执行引擎，真正的控制面在这一层。
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict, Iterator, List

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agent_framework.bootstrap.injector import BootstrapInjector
from agent_framework.bootstrap.loader import BootstrapLoader
from agent_framework.config.settings import FrameworkSettings, get_settings
from agent_framework.core.agent import AgentSpec
from agent_framework.core.events import EventBus
from agent_framework.core.session_manager import SessionManager
from agent_framework.core.subagents import SubagentManager
from agent_framework.memory import MemoryManager, SQLiteLongTermMemoryStore, SQLiteShortTermMemoryStore
from agent_framework.memory.models import SessionStateRecord
from agent_framework.plugins.loader import PluginLoader
from agent_framework.skills import SkillRegistry, SkillRouter, SkillRuntime
from agent_framework.tools import (
    ApprovalManager,
    AuditLogger,
    ToolExecutor,
    ToolPolicyEngine,
    ToolRegistry,
)
from agent_framework.workflows.common import WorkflowRunner, WorkflowStreamEvent
from agent_framework.workflows.common.nodes import WorkflowNodes


class Gateway:
    """运行时控制面。

    它统一管理 agent 注册、session 生命周期、bootstrap 注入、skill routing、
    tool governance、memory 落盘和 workflow 执行。
    """

    def __init__(self, settings: FrameworkSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_storage_dirs()
        self.logger = logging.getLogger("agent_framework")
        self.event_bus = EventBus(self.logger)
        self.short_term_memory_store = SQLiteShortTermMemoryStore(self.settings.database_path)
        self.long_term_memory_store = SQLiteLongTermMemoryStore(self.settings.database_path)
        self.memory_manager = MemoryManager(
            self.short_term_memory_store, self.long_term_memory_store, settings=self.settings
        )
        self.session_manager = SessionManager(self.memory_manager)
        self.bootstrap_loader = BootstrapLoader(self.settings)
        self.bootstrap_injector = BootstrapInjector()
        self.tool_registry = ToolRegistry()
        self.tool_policy_engine = ToolPolicyEngine()
        self.approval_manager = ApprovalManager()
        self.audit_logger = AuditLogger()
        self.tool_executor = ToolExecutor(
            registry=self.tool_registry,
            policy_engine=self.tool_policy_engine,
            approval_manager=self.approval_manager,
            audit_logger=self.audit_logger,
        )
        self.plugin_loader = PluginLoader()
        self.agent_specs: Dict[str, AgentSpec] = {}
        self.subagents = SubagentManager(self)
        # 默认把运行时事件写回 session event log，便于后续追踪和审计。
        self.event_bus.subscribe(
            lambda event: self.memory_manager.log_event(
                event.payload.get("session_id", "system"),
                event.event_type,
                event.payload,
            )
        )

    def register_agent(self, spec: AgentSpec, tools: List[object] | None = None) -> None:
        self.agent_specs[spec.agent_id] = spec
        if tools:
            for tool in tools:
                self.tool_registry.register(tool)

    def get_agent(self, agent_id: str) -> AgentSpec:
        if agent_id not in self.agent_specs:
            raise KeyError(f"unknown agent: {agent_id}")
        return self.agent_specs[agent_id]

    def _persist_intermediate_builder_state(
        self,
        session_id: str,
        summary: str,
        active_skills: List[str],
        working_state: Dict[str, object],
    ) -> None:
        """builder 中间状态先落盘，避免本轮异常中断后丢失待确认 blueprint。"""

        next_state = SessionStateRecord(
            session_id=session_id,
            summary=summary,
            active_skills=active_skills,
            working_state=working_state,
        )
        self.session_manager.save_state(next_state)

    def _prepare_run(
        self,
        *,
        agent_id: str,
        user_input: str,
        session_id: str | None,
        task_brief: str | None,
        tool_whitelist: List[str] | None,
        parent_session_id: str | None,
        subagent_mode: bool,
    ) -> tuple[AgentSpec, str, WorkflowRunner, List[object], SessionStateRecord]:
        spec = self.get_agent(agent_id)
        run_session_id = session_id or str(uuid.uuid4())
        self.session_manager.open(run_session_id, agent_id, parent_session_id)
        self.session_manager.append_user_message(run_session_id, user_input)
        snapshot = self.bootstrap_loader.load_workspace(spec.workspace_dir)

        skill_registry = SkillRegistry()
        for directory in spec.skills_dirs:
            skill_registry.load_directory(directory)
        skill_runtime = SkillRuntime(self.settings, self.tool_registry)
        skill_router = SkillRouter(max_active_skills=spec.max_active_skills)

        messages = self.session_manager.load_messages(run_session_id)
        recent_messages = messages[-self.settings.max_history_messages :]
        state = self.session_manager.load_state(run_session_id)

        self.event_bus.emit(
            "run.started",
            {"agent_id": agent_id, "session_id": run_session_id, "subagent_mode": subagent_mode},
        )
        self.event_bus.emit(
            "bootstrap.injected",
            {
                "agent_id": agent_id,
                "session_id": run_session_id,
                "workspace_dir": str(spec.workspace_dir),
                "documents": [name for name, document in snapshot.documents.items() if document.content.strip()],
            },
        )

        nodes = WorkflowNodes(
            settings=self.settings,
            agent_spec=spec,
            memory_manager=self.memory_manager,
            skill_registry=skill_registry,
            skill_router=skill_router,
            skill_runtime=skill_runtime,
            bootstrap_snapshot=snapshot,
            bootstrap_injector=self.bootstrap_injector,
            tool_executor=self.tool_executor,
            tool_policy=spec.tool_policy,
            llm=spec.llm,
            tool_whitelist=tool_whitelist,
            event_bus=self.event_bus,
            intermediate_state_persist=self._persist_intermediate_builder_state,
        )
        runner = WorkflowRunner(nodes, max_iterations=self.settings.max_tool_iterations)
        return spec, run_session_id, runner, recent_messages, state

    def _persist_workflow_result(
        self,
        *,
        agent_id: str,
        session_id: str,
        new_messages: List[BaseMessage],
        summary: str,
        active_skills: List[str],
        working_state: Dict[str, object],
        response_text: str,
    ) -> None:
        # 这里只持久化 run 新产生的消息，避免重复写入之前已经存在的 transcript。
        for message in new_messages:
            if isinstance(message, AIMessage) and not message.tool_calls:
                self.session_manager.append_assistant_message(session_id, str(message.content))
            elif isinstance(message, ToolMessage):
                self.session_manager.append_tool_message(session_id, str(message.content))

        next_state = SessionStateRecord(
            session_id=session_id,
            summary=summary,
            active_skills=active_skills,
            working_state=working_state,
        )
        self.session_manager.save_state(next_state)
        self.event_bus.emit(
            "run.completed",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "active_skills": active_skills,
                "response_text": response_text,
            },
        )

        # 触发反思和经验提炼
        self._trigger_reflection(agent_id, session_id, new_messages, summary)

    def _trigger_reflection(
        self,
        agent_id: str,
        session_id: str,
        messages: List[BaseMessage],
        summary: str,
    ) -> None:
        """触发反思和经验提炼流程。"""
        # 检查是否启用反思
        if not getattr(self.settings, "memory_reflection_enabled", True):
            return

        # 检查消息数量是否足够
        if len(messages) < 3:
            return

        # 检查是否有工具调用（更值得反思）
        has_tool_calls = any(isinstance(msg, ToolMessage) for msg in messages)
        if not has_tool_calls and len(messages) < 5:
            return

        try:
            # 获取Agent的LLM
            spec = self.get_agent(agent_id)
            llm = spec.llm

            # 执行反思
            self.memory_manager.reflect_and_store(
                session_id=session_id,
                agent_id=agent_id,
                messages=messages,
                llm=llm,
                summary=summary,
            )
        except Exception:
            self.logger.debug("触发反思失败")

    def run(
        self,
        *,
        agent_id: str,
        user_input: str,
        session_id: str | None = None,
        task_brief: str | None = None,
        tool_whitelist: List[str] | None = None,
        parent_session_id: str | None = None,
        subagent_mode: bool = False,
    ) -> str:
        """执行一次 agent run，并把新消息与新状态写回存储层。"""
        spec, run_session_id, runner, recent_messages, state = self._prepare_run(
            agent_id=agent_id,
            user_input=user_input,
            session_id=session_id,
            task_brief=task_brief,
            tool_whitelist=tool_whitelist,
            parent_session_id=parent_session_id,
            subagent_mode=subagent_mode,
        )
        result = runner.run(
            session_id=run_session_id,
            user_input=user_input,
            task_brief=task_brief or "",
            messages=recent_messages,
            summary=state.summary,
            working_state=state.working_state,
        )
        self._persist_workflow_result(
            agent_id=spec.agent_id,
            session_id=run_session_id,
            new_messages=result.new_messages,
            summary=result.summary,
            active_skills=result.active_skills,
            working_state=result.working_state,
            response_text=result.response_text,
        )
        return result.response_text

    def stream(
        self,
        *,
        agent_id: str,
        user_input: str,
        session_id: str | None = None,
        task_brief: str | None = None,
        tool_whitelist: List[str] | None = None,
        parent_session_id: str | None = None,
        subagent_mode: bool = False,
    ) -> Iterator[WorkflowStreamEvent]:
        """以流式事件形式执行一次 agent run。"""

        spec, run_session_id, runner, recent_messages, state = self._prepare_run(
            agent_id=agent_id,
            user_input=user_input,
            session_id=session_id,
            task_brief=task_brief,
            tool_whitelist=tool_whitelist,
            parent_session_id=parent_session_id,
            subagent_mode=subagent_mode,
        )
        try:
            for event in runner.stream(
                session_id=run_session_id,
                user_input=user_input,
                task_brief=task_brief or "",
                messages=recent_messages,
                summary=state.summary,
                working_state=state.working_state,
            ):
                if event.event_type == "run_completed":
                    payload = event.payload
                    self._persist_workflow_result(
                        agent_id=spec.agent_id,
                        session_id=run_session_id,
                        new_messages=payload["new_messages"],
                        summary=payload["summary"],
                        active_skills=payload["active_skills"],
                        working_state=payload["working_state"],
                        response_text=payload["response_text"],
                    )
                yield event
        except Exception as exc:  # noqa: BLE001
            self.event_bus.emit(
                "run.failed",
                {"agent_id": agent_id, "session_id": run_session_id, "error": str(exc)},
            )
            yield WorkflowStreamEvent(
                "run_failed",
                {"agent_id": agent_id, "session_id": run_session_id, "error": str(exc)},
            )
