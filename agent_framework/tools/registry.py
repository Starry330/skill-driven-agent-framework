from typing import Dict, List, Any, Optional
from langchain_core.tools import BaseTool

class LocalToolRegistry:
    """
    A local registry for tools, acting as a mock MCP server.
    It allows registering tools and executing them.
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool in the registry."""
        self._tools[tool.name] = tool

    def get_tools(self) -> List[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a specific tool by name."""
        return self._tools.get(name)

    def execute_tool(self, name: str, tool_input: Any) -> Any:
        """Execute a tool by name with the given input."""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool {name} not found")
        return tool.invoke(tool_input)
