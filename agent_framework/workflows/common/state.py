"""LangGraph workflow 使用的状态与流式事件结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Dict, List, TypedDict

from langgraph.graph.message import add_messages


@dataclass(slots=True)
class WorkflowStreamEvent:
    """workflow 对外暴露的流式事件。"""

    event_type: str
    payload: Dict[str, Any]


class WorkflowState(TypedDict):
    """单次 workflow run 中跨节点流转的共享状态。"""

    session_id: str
    user_input: str
    task_brief: str
    messages: Annotated[List[Any], add_messages]
    summary: str
    memory_hits: List[str]
    active_skills: List[str]
    working_state: Dict[str, Any]
    stop_after_tools: bool
    iteration_count: int
    visible_tool_names: List[str]
