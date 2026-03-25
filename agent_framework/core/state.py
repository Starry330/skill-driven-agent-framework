from typing import TypedDict, List, Dict, Any, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Represents the state of the agent.
    """
    messages: Annotated[List[Any], add_messages]
    context: Dict[str, Any]
    active_skills: List[str]
    summary: str
