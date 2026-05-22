from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool

from agent_framework.tools.registry import ToolRegistry


class MCPClient:
    def __init__(self, registry: Optional[ToolRegistry] = None) -> None:
        self._tools: Dict[str, BaseTool] = {}
        if registry is not None:
            for tool_name in registry.names():
                self._tools[tool_name] = registry.get_base_tool(tool_name)

    def register_tool(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_tools(self) -> List[BaseTool]:
        return self.list_tools()

    def call_tool(self, name: str, payload: Dict[str, Any]) -> Any:
        tool = self._tools[name]
        return tool.invoke(payload)

    def execute_tool(self, name: str, payload: Dict[str, Any]) -> Any:
        return self.call_tool(name, payload)
