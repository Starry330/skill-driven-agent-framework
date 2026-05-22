from __future__ import annotations

from agent_framework.mcp.client import MCPClient
from agent_framework.tools.adapters.mcp import build_mcp_tool_spec
from agent_framework.tools.registry import ToolRegistry


class MCPToolAdapter:
    def __init__(self, client: MCPClient) -> None:
        self.client = client

    def register_into(self, registry: ToolRegistry) -> None:
        for tool in self.client.list_tools():
            registry.register(build_mcp_tool_spec(tool))
