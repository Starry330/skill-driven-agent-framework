"""审批抽象层。

当前默认实现始终放行，但边界已经固定在这里，后续可以接 HITL 或策略引擎而不改
 ToolExecutor 主链路。
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_framework.tools.models import ToolExecutionContext, ToolSpec


@dataclass(slots=True)
class ApprovalDecision:
    """工具审批结果。"""

    approved: bool
    reason: str | None = None


class ApprovalManager:
    """审批入口。

    之所以保留独立类，而不是把逻辑写进 policy，是为了把“是否需要审批”和
    “审批是否通过”这两个阶段分开。
    """

    def approve(self, tool: ToolSpec, context: ToolExecutionContext) -> ApprovalDecision:
        return ApprovalDecision(approved=True)
