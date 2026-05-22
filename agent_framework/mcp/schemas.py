from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class MCPToolSchema:
    name: str
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPToolCallError:
    message: str
    code: str = "MCP_TOOL_ERROR"
