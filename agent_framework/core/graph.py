from typing import List, Optional, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.language_models import BaseChatModel
from agent_framework.core.state import AgentState
from agent_framework.core.workflow import WorkflowNodes
from agent_framework.soul.models import Soul
from agent_framework.skills.registry import SkillRegistry
from agent_framework.memory.psych_mem import PsychMem
from agent_framework.mcp.client import MCPClient
from agent_framework.mcp.tool_node import create_tool_node
from agent_framework.memory.short_term import get_checkpointer

def create_agent_graph(
    soul: Soul, 
    skills: SkillRegistry, 
    memory: PsychMem, 
    mcp: MCPClient, 
    llm: BaseChatModel,
    interrupt_before_tools: bool = False
) -> Any:
    """
    Creates and compiles the agent graph.
    
    Args:
        soul: The agent's soul (persona).
        skills: The skill registry.
        memory: The memory system (PsychMem).
        mcp: The MCP client for tools.
        llm: The LLM to use.
        interrupt_before_tools: Whether to interrupt before executing tools (HITL).
        
    Returns:
        The compiled graph.
    """
    
    # Initialize nodes
    workflow_nodes = WorkflowNodes(soul, skills, memory, mcp, llm)
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("retrieve", workflow_nodes.retrieve)
    workflow.add_node("agent", workflow_nodes.agent)
    
    tools = mcp.get_tools()
    tool_node = create_tool_node(tools)
    workflow.add_node("tools", tool_node)
    
    workflow.add_node("summarize", workflow_nodes.summarize)
    
    # Add edges
    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "agent")
    
    # Conditional edges from agent
    def should_continue(state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return "summarize"
            
        last_message = messages[-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        return "summarize"

    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "summarize": "summarize"
        }
    )
    
    workflow.add_edge("tools", "agent")
    workflow.add_edge("summarize", END)
    
    # Compile
    checkpointer = get_checkpointer()
    
    interrupt_before = ["tools"] if interrupt_before_tools else []
    
    app = workflow.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)
    
    return app
