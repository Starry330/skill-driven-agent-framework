"""工具访问策略。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agent_framework.tools.models import ToolExecutionContext, ToolSpec


@dataclass(slots=True)
class ToolPolicy:
    """agent 级和 skill 级工具约束。"""

    allowlist: Optional[List[str]] = None
    denylist: List[str] = field(default_factory=list)
    skill_tool_overrides: Dict[str, List[str]] = field(default_factory=dict)
    approval_required_for: List[str] = field(default_factory=lambda: ["high", "critical"])


@dataclass(slots=True)
class ToolPolicyDecision:
    """策略引擎的标准判断结果。"""

    allowed: bool
    reason: str | None = None
    approval_required: bool = False


class ToolPolicyEngine:
    """组合多个策略来源，决定一个工具是否允许执行。"""

    def evaluate(
        self,
        tool: ToolSpec,
        context: ToolExecutionContext,
        policy: ToolPolicy,
    ) -> ToolPolicyDecision:
        # denylist 优先级最高，用于显式封禁高风险工具。
        if tool.name in policy.denylist:
            return ToolPolicyDecision(allowed=False, reason="tool is denylisted")

        # session 白名单通常用于 sub-agent 或特定 run 的临时能力收窄。
        if context.tool_whitelist is not None and tool.name not in context.tool_whitelist:
            return ToolPolicyDecision(allowed=False, reason="tool is not in session whitelist")

        if context.requires_active_skill and not context.active_skills:
            return ToolPolicyDecision(
                allowed=False,
                reason="agent requires an active skill before tool use",
            )

        # agent allowlist 决定该 agent 的全局能力边界。
        if policy.allowlist is not None and tool.name not in policy.allowlist:
            return ToolPolicyDecision(allowed=False, reason="tool is not in agent allowlist")

        if context.active_skills:
            # 多个 active skills 同时存在时，按“显式允许集合并集”收口。
            # 否则某个辅助 skill 的 override 会反向阻断真正负责执行的 skill。
            scoped_overrides = [
                allowed_tools
                for skill_name in context.active_skills
                if (allowed_tools := policy.skill_tool_overrides.get(skill_name)) is not None
            ]
            if scoped_overrides:
                allowed_union = {name for allowed_tools in scoped_overrides for name in allowed_tools}
                if tool.name not in allowed_union:
                    return ToolPolicyDecision(
                        allowed=False,
                        reason="tool is not permitted by active skill policy",
                    )

        return ToolPolicyDecision(
            allowed=True,
            approval_required=tool.side_effect_level in policy.approval_required_for,
        )
