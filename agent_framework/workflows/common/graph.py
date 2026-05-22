"""LangGraph 执行图封装。

workflow 只负责一次 run 内的状态推进，不承担 session、registry 或持久化控制职责。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Sequence

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph

from agent_framework.workflows.common.nodes import WorkflowNodes
from agent_framework.workflows.common.state import WorkflowState, WorkflowStreamEvent


@dataclass(slots=True)
class WorkflowRunResult:
    """workflow 执行完成后返回给 Gateway 的摘要结果。"""

    new_messages: List[BaseMessage]
    summary: str
    active_skills: List[str]
    working_state: Dict[str, Any]
    response_text: str


class WorkflowRunner:
    """构建并运行 LangGraph 状态图。"""

    def __init__(self, nodes: WorkflowNodes, max_iterations: int = 15) -> None:
        self.nodes = nodes
        self.max_iterations = max_iterations
        self._graph = self._build_graph()

    def _build_graph(self):
        max_iterations = self.max_iterations

        # 节点顺序刻意固定为 retrieve -> route -> agent -> tools -> summarize。
        graph = StateGraph(WorkflowState)
        graph.add_node("retrieve_context", self.nodes.retrieve_context)
        graph.add_node("route_skills", self.nodes.route_skills)
        graph.add_node("agent", self.nodes.agent)
        graph.add_node("tools", self.nodes.tools)
        graph.add_node("summarize", self.nodes.summarize)

        graph.add_edge(START, "retrieve_context")
        graph.add_edge("retrieve_context", "route_skills")
        graph.add_edge("route_skills", "agent")

        def should_continue(state: WorkflowState) -> str:
            # 只有最后一条 AIMessage 含 tool_calls 时才进入 tools 节点，否则直接收束。
            messages = state.get("messages", [])
            if not messages:
                return "summarize"
            last_message = messages[-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"
            return "summarize"

        graph.add_conditional_edges("agent", should_continue, {"tools": "tools", "summarize": "summarize"})

        def should_continue_after_tools(state: WorkflowState) -> str:
            if state.get("stop_after_tools", False):
                return "summarize"
            iteration_count = state.get("iteration_count", 0)
            if iteration_count >= max_iterations:
                return "summarize"
            return "agent"

        graph.add_conditional_edges("tools", should_continue_after_tools, {"agent": "agent", "summarize": "summarize"})
        graph.add_edge("summarize", END)
        return graph.compile()

    def _initial_state(
        self,
        *,
        session_id: str,
        user_input: str,
        task_brief: str,
        messages: Sequence[BaseMessage],
        summary: str,
        working_state: dict,
    ) -> WorkflowState:
        return {
            "session_id": session_id,
            "user_input": user_input,
            "task_brief": task_brief,
            "messages": list(messages),
            "summary": summary,
            "memory_hits": [],
            "active_skills": [],
            "working_state": dict(working_state),
            "stop_after_tools": False,
            "iteration_count": 0,
        }

    def _apply_updates(self, state: WorkflowState, updates: Dict[str, Any]) -> WorkflowState:
        next_state = dict(state)
        for key, value in updates.items():
            if key == "messages":
                next_state["messages"] = list(next_state.get("messages", [])) + list(value)
                continue
            next_state[key] = value
        return next_state  # type: ignore[return-value]

    def _build_result(self, final_state: WorkflowState, initial_count: int, fallback_summary: str) -> WorkflowRunResult:
        final_messages = list(final_state.get("messages", []))
        new_messages = final_messages[initial_count:]
        response_text = ""
        for message in reversed(new_messages):
            if isinstance(message, AIMessage) and not message.tool_calls:
                response_text = str(message.content)
                break
        return WorkflowRunResult(
            new_messages=new_messages,
            summary=final_state.get("summary", fallback_summary),
            active_skills=list(final_state.get("active_skills", [])),
            working_state=dict(final_state.get("working_state", {})),
            response_text=response_text,
        )

    def run(
        self,
        *,
        session_id: str,
        user_input: str,
        task_brief: str,
        messages: Sequence[BaseMessage],
        summary: str,
        working_state: dict,
    ) -> WorkflowRunResult:
        initial_count = len(messages)
        final_state = self._graph.invoke(
            self._initial_state(
                session_id=session_id,
                user_input=user_input,
                task_brief=task_brief,
                messages=messages,
                summary=summary,
                working_state=working_state,
            )
        )
        return self._build_result(final_state, initial_count, summary)

    def stream(
        self,
        *,
        session_id: str,
        user_input: str,
        task_brief: str,
        messages: Sequence[BaseMessage],
        summary: str,
        working_state: dict,
    ) -> Iterator[WorkflowStreamEvent]:
        initial_count = len(messages)
        state = self._initial_state(
            session_id=session_id,
            user_input=user_input,
            task_brief=task_brief,
            messages=messages,
            summary=summary,
            working_state=working_state,
        )

        state = self._apply_updates(state, self.nodes.retrieve_context(state))
        state = self._apply_updates(state, self.nodes.route_skills(state))

        while True:
            for event in self.nodes.agent_stream(state):
                if event.event_type == "agent_updates":
                    state = self._apply_updates(state, event.payload["updates"])
                    continue
                yield event

            messages_after_agent = state.get("messages", [])
            if not messages_after_agent:
                break

            last_message = messages_after_agent[-1]
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                for event in self.nodes.tools_stream(state):
                    if event.event_type == "tool_updates":
                        state = self._apply_updates(state, event.payload["updates"])
                        continue
                    yield event
                if state.get("stop_after_tools", False):
                    break
                # Increment iteration count after tools execution
                current_count = state.get("iteration_count", 0)
                state = self._apply_updates(state, {"iteration_count": current_count + 1})
                if state.get("iteration_count", 0) >= self.max_iterations:
                    break
                continue
            break

        state = self._apply_updates(state, self.nodes.summarize(state))
        result = self._build_result(state, initial_count, summary)
        yield WorkflowStreamEvent(
            "run_completed",
            {
                "new_messages": result.new_messages,
                "summary": result.summary,
                "active_skills": result.active_skills,
                "working_state": result.working_state,
                "response_text": result.response_text,
            },
        )
