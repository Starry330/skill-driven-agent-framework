from __future__ import annotations

from langchain_core.tools import BaseTool

from agent_framework.tools.models import ToolSpec


def build_mcp_tool_spec(tool: BaseTool) -> ToolSpec:
    return ToolSpec(
        name=tool.name,
        description=tool.description,
        base_tool=tool,
        side_effect_level="medium",
        workspace_scope="external",
    )
