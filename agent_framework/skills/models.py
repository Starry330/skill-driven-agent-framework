from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class Skill(BaseModel):
    """
    Represents a skill that an agent can perform.
    
    A skill is defined by its metadata (name, description, parameters) and its body (prompt/implementation).
    """
    name: str = Field(..., description="The name of the skill")
    description: str = Field(..., description="A description of what the skill does")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for the skill's parameters")
    body: str = Field(..., description="The actual implementation or prompt for the skill")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the skill")
