from typing import List, Optional
from pydantic import BaseModel, Field

class Guardrail(BaseModel):
    """Represents a guardrail for the agent's behavior."""
    name: str = Field(..., description="The name of the guardrail")
    description: str = Field(..., description="A description of what the guardrail enforces")
    rules: List[str] = Field(default_factory=list, description="A list of specific rules associated with this guardrail")

class Soul(BaseModel):
    """Represents the 'soul' or persona of an agent."""
    role: str = Field(..., description="The role of the agent (e.g., 'Research Assistant')")
    goal: str = Field(..., description="The primary goal of the agent")
    backstory: str = Field(..., description="The backstory of the agent to give it context and personality")
    style: List[str] = Field(default_factory=list, description="A list of style guidelines for the agent's responses")
    guardrails: List[Guardrail] = Field(default_factory=list, description="A list of guardrails to enforce behavior")
    system_prompt: Optional[str] = Field(None, description="The full system prompt template, usually loaded from the markdown body")
