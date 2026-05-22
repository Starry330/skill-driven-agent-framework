from __future__ import annotations

from langchain_core.tools import BaseTool

from agent_framework.tools.models import ToolSpec


def build_local_tool_spec(
    tool: BaseTool,
    *,
    side_effect_level: str = "low",
    workspace_scope: str = "workspace",
    timeout_seconds: int = 30,
) -> ToolSpec:
    return ToolSpec(
        name=tool.name,
        description=tool.description,
        base_tool=tool,
        side_effect_level=side_effect_level,
        workspace_scope=workspace_scope,
        timeout_seconds=timeout_seconds,
    )
