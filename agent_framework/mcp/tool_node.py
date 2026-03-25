from typing import List, Callable, Any, Optional
import functools
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import ToolNode

def sandbox_exec(func: Callable, *args: Any, **kwargs: Any) -> Any:
    """
    Execute a function in a simulated sandbox environment.
    """
    print(f"Running in sandbox...")
    return func(*args, **kwargs)

def _wrap_tool_with_sandbox(tool: BaseTool) -> BaseTool:
    """
    Wrap a tool to execute in the sandbox.
    If the tool has a 'func' attribute (e.g. StructuredTool), wrap that.
    Otherwise, wrap '_run'.
    """
    if hasattr(tool, "func") and callable(tool.func):
        # StructuredTool typically stores the function in .func
        original_func = tool.func
        
        @functools.wraps(original_func)
        def sandboxed_func(*args, **kwargs):
            return sandbox_exec(original_func, *args, **kwargs)
        
        tool.func = sandboxed_func
        return tool
    
    # Fallback for other BaseTools
    original_run = tool._run
    
    # We explicitly accept config to ensure it's passed if invoke provides it
    def sandboxed_run(*args, config: Optional[RunnableConfig] = None, **kwargs):
        # Pass config to original_run if it was provided
        if config is not None:
            kwargs['config'] = config
        
        # Call the original run method via sandbox wrapper
        return sandbox_exec(original_run, *args, **kwargs)
    
    tool._run = sandboxed_run
    return tool

def create_tool_node(tools: List[BaseTool]) -> ToolNode:
    """
    Create a LangGraph ToolNode with the given tools, wrapped in sandbox execution.
    """
    # Note: We are modifying tools in-place. If the same tool instances are used elsewhere,
    # they will also be sandboxed. This is likely acceptable for this use case.
    sandboxed_tools = [_wrap_tool_with_sandbox(tool) for tool in tools]
    return ToolNode(sandboxed_tools)
