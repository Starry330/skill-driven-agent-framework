"""skill 运行时模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(slots=True)
class SkillSpec:
    """描述一个可路由的 skill。

    skill 是任务能力单元，不是 tool。它声明触发条件、所需工具和正文指令，
    最终由 skill runtime 决定是否可用、是否被激活。

    支持两种触发模式：
    1. 显式触发：用户输入 /slash-command 格式
    2. 隐式触发：基于 triggers 列表的关键词匹配
    """

    name: str
    description: str
    body: str
    path: Path
    triggers: List[str] = field(default_factory=list)
    slash_command: str = ""  # 显式 slash command 名称，如 "search" 对应 /search
    required_tools: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    input_schema: Dict[str, object] = field(default_factory=dict)
    output_schema: Dict[str, object] = field(default_factory=dict)
    decision_logic: List[Dict[str, object]] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    failure_modes: List[Dict[str, object]] = field(default_factory=list)
    fallback_strategy: List[Dict[str, object]] = field(default_factory=list)
    tool_policy: Dict[str, object] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    availability_checks: List[str] = field(default_factory=list)
    subagent_allowed: bool = False
    enabled: bool = True
    metadata: Dict[str, object] = field(default_factory=dict)
    routing_score: float = 0.0
    available: bool = True
    unavailable_reason: str | None = None

    def render_protocol_prompt(self) -> str:
        """把协议字段渲染成统一的 prompt section。"""

        protocol: Dict[str, Any] = {
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "decision_logic": self.decision_logic,
            "constraints": self.constraints,
            "failure_modes": self.failure_modes,
            "fallback_strategy": self.fallback_strategy,
            "tool_policy": self.tool_policy,
            "required_tools": self.required_tools,
            "permissions": self.permissions,
        }
        lines = ["skill_protocol:"]
        for key, value in protocol.items():
            lines.append(f"- {key}: {value}")
        if self.body.strip():
            lines.append("")
            lines.append("skill_body:")
            lines.append(self.body.strip())
        return "\n".join(lines)
