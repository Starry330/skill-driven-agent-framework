from typing import List, Any, Optional
from langchain_core.tools import BaseTool
from agent_framework.tools.registry import LocalToolRegistry

class MCPClient:
    """
    A client for interacting with Model Context Protocol (MCP) servers.
    Currently, it uses a LocalToolRegistry as a mock server.
    """
    def __init__(self, registry: Optional[LocalToolRegistry] = None):
        """
        Initialize the MCP Client.
        
        Args:
            registry: A LocalToolRegistry instance acting as a mock server.
                      If not provided, a new empty registry is created.
        """
        self.registry = registry or LocalToolRegistry()

    def get_tools(self) -> List[BaseTool]:
        """Get tools from the MCP server (registry)."""
        return self.registry.get_tools()

    def execute_tool(self, name: str, args: Any) -> Any:
        """Execute a tool on the MCP server (registry)."""
        return self.registry.execute_tool(name, args)
