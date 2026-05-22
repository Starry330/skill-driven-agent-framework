from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool


@dataclass(slots=True)
class RetryPolicy:
    attempts: int = 1


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    base_tool: BaseTool
    side_effect_level: str = "low"
    workspace_scope: str = "workspace"
    timeout_seconds: int = 30
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    tags: List[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolExecutionContext:
    agent_id: str
    session_id: str
    active_skills: List[str] = field(default_factory=list)
    tool_whitelist: Optional[List[str]] = None
    requires_active_skill: bool = False
    dry_run: bool = False


@dataclass(slots=True)
class ToolExecutionResult:
    ok: bool
    output: Any = None
    error: str | None = None
    denied: bool = False
    approval_required: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
