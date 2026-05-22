"""工具执行审计。"""

from __future__ import annotations

from typing import Any, Dict

from agent_framework.tools.models import ToolExecutionContext, ToolExecutionResult, ToolSpec


class AuditLogger:
    """收集工具执行结果的审计记录。"""

    def __init__(self) -> None:
        self.records: list[Dict[str, Any]] = []

    def log(self, tool: ToolSpec, context: ToolExecutionContext, result: ToolExecutionResult) -> None:
        # 审计记录保留“谁、在什么 session、以什么 skill 背景调用了什么工具”。
        self.records.append(
            {
                "tool": tool.name,
                "agent_id": context.agent_id,
                "session_id": context.session_id,
                "skills": list(context.active_skills),
                "ok": result.ok,
                "error": result.error,
                "denied": result.denied,
                "approval_required": result.approval_required,
                "metadata": dict(result.metadata),
            }
        )
