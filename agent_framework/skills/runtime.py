"""skill 可用性与激活逻辑。"""

from __future__ import annotations

from dataclasses import replace
from typing import List, Sequence

from agent_framework.config.settings import FrameworkSettings
from agent_framework.skills.models import SkillSpec
from agent_framework.tools.registry import ToolRegistry


class SkillRuntime:
    """负责把“候选 skill”变成“本轮可用 skill”。

    重点是把配置缺失、工具未注册等运行时条件挡在 prompt 注入之前，而不是等模型
    真的尝试调用时才失败。
    """

    def __init__(self, settings: FrameworkSettings, tool_registry: ToolRegistry) -> None:
        self.settings = settings
        self.tool_registry = tool_registry

    def apply_availability(self, skills: Sequence[SkillSpec]) -> List[SkillSpec]:
        available: List[SkillSpec] = []
        for skill in skills:
            evaluated = replace(skill)
            # required_tools 是 skill 能否进入本轮上下文的硬前置条件。
            missing_tools = [name for name in evaluated.required_tools if self.tool_registry.get(name) is None]
            if missing_tools:
                evaluated.available = False
                evaluated.unavailable_reason = f"missing tools: {', '.join(missing_tools)}"
                continue
            if "requires_web_search" in evaluated.availability_checks and not self.settings.web_search_url:
                evaluated.available = False
                evaluated.unavailable_reason = "web search provider is not configured"
                continue
            available.append(evaluated)
        return available

    def activate(self, skills: Sequence[SkillSpec], allow_subagent: bool = False) -> List[SkillSpec]:
        filtered = self.apply_availability(skills)
        if allow_subagent:
            # 子代理只继承显式允许下放的能力，避免默认放大全部技能面。
            return [skill for skill in filtered if skill.subagent_allowed]
        return filtered
