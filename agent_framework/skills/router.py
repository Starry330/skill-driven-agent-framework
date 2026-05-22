"""基于用户输入的轻量 skill 路由器。

采用渐进式披露设计：支持显式 slash command 触发和隐式关键词触发。
仿照 Claude Code 的 skill 触发机制。
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Dict, List, Optional, Sequence

from agent_framework.skills.models import SkillSpec


STAGE_TO_SKILL: Dict[str, List[str]] = {
    "requirements_collection": ["collect-agent-requirements"],
    "requirements_collected": ["design-agent-blueprint"],
    "blueprint_drafted": ["finalize-blueprint"],
    "awaiting_confirmation": ["finalize-blueprint"],
}

# Slash command 前缀
SLASH_PREFIX = "/"

# 帮助命令
HELP_COMMAND = "/help"


class SkillRouter:
    """根据用户输入挑选候选 skill。

    支持两种触发模式：
    1. 显式触发：用户输入 /skill-name 格式的 slash command
    2. 隐式触发：基于触发词和文本重合度的启发式评分

    对于 builder agent，还会根据 builder_state.stage 来强制激活对应的 skill。
    """

    def __init__(self, max_active_skills: int = 2) -> None:
        self.max_active_skills = max_active_skills

    def route(
        self,
        user_input: str,
        skills: Sequence[SkillSpec],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[SkillSpec]:
        """路由用户输入到对应的 skill。

        优先级：
        1. Builder agent 的状态机强制路由
        2. 显式 slash command 触发（/skill-name）
        3. 隐式关键词触发（启发式评分）
        """
        query = user_input.strip()
        skill_map = {skill.name: skill for skill in skills}

        # 1. Builder agent 的状态机强制路由
        stage_forced_skills: List[str] = []
        if context is not None:
            builder_state = context.get("builder_state", {})
            if "stage" in builder_state and builder_state["stage"]:
                stage = builder_state["stage"]
                if stage in STAGE_TO_SKILL:
                    stage_forced_skills = STAGE_TO_SKILL[stage]

        if stage_forced_skills:
            result: List[SkillSpec] = []
            for skill_name in stage_forced_skills:
                if skill_name in skill_map:
                    forced_skill = replace(skill_map[skill_name])
                    forced_skill.routing_score = 100.0
                    result.append(forced_skill)
            return result

        # 2. 显式 slash command 触发
        if query.startswith(SLASH_PREFIX):
            return self._handle_slash_command(query, skills)

        # 3. 隐式关键词触发
        return self._handle_implicit_trigger(query, skills)

    def _handle_slash_command(
        self,
        query: str,
        skills: Sequence[SkillSpec],
    ) -> List[SkillSpec]:
        """处理显式 slash command。

        支持格式：
        - /skill-name：激活指定 skill
        - /slash-command：使用 skill 定义的 slash_command 激活
        - /help：返回空列表（由调用方处理帮助信息）
        """
        command = query[len(SLASH_PREFIX) :].strip().lower()

        # 处理帮助命令
        if command == "help" or command == "":
            return []

        # 构建两种索引：name 和 slash_command
        skill_map_by_name = {skill.name.lower(): skill for skill in skills}
        skill_map_by_slash = {
            skill.slash_command.lower(): skill
            for skill in skills
            if skill.slash_command
        }

        # 1. 精确匹配 skill name
        if command in skill_map_by_name:
            matched_skill = replace(skill_map_by_name[command])
            matched_skill.routing_score = 100.0
            return [matched_skill]

        # 2. 精确匹配 slash_command
        if command in skill_map_by_slash:
            matched_skill = replace(skill_map_by_slash[command])
            matched_skill.routing_score = 100.0
            return [matched_skill]

        # 3. 模糊匹配（支持部分名称匹配）
        for skill_name, skill in skill_map_by_name.items():
            if command in skill_name or skill_name in command:
                matched_skill = replace(skill)
                matched_skill.routing_score = 90.0
                return [matched_skill]

        # 未找到匹配的 skill，返回空列表
        return []

    def _handle_implicit_trigger(
        self,
        query: str,
        skills: Sequence[SkillSpec],
    ) -> List[SkillSpec]:
        """处理隐式关键词触发。"""
        scored: List[SkillSpec] = []
        query_lower = query.lower()
        query_terms = set(re.findall(r"[a-zA-Z0-9_\-一-鿿]+", query_lower))

        for skill in skills:
            score = 0.0

            # 触发词匹配
            for trigger in skill.triggers:
                trigger_lower = trigger.lower()
                if trigger_lower in query_lower:
                    score += 5.0
                if trigger_lower in query_terms:
                    score += 2.0

            # Skill 名称匹配
            for term in re.findall(r"[a-zA-Z0-9_\-一-鿿]+", skill.name.lower()):
                if term in query_terms:
                    score += 1.5

            # Skill 描述匹配
            for term in re.findall(r"[a-zA-Z0-9_\-一-鿿]+", skill.description.lower()):
                if term in query_terms:
                    score += 0.25

            candidate = replace(skill)
            candidate.routing_score = score
            if score > 0:
                scored.append(candidate)

        scored.sort(key=lambda item: item.routing_score, reverse=True)
        return scored[: self.max_active_skills]

    def get_available_skills_help(self, skills: Sequence[SkillSpec]) -> str:
        """生成可用 skill 的帮助信息。

        仿照 Claude Code 的 /help 格式。
        """
        if not skills:
            return "没有可用的 skill。"

        lines = ["可用的 skill：", ""]
        for skill in skills:
            if skill.enabled:
                # 显示 slash_command（如果有）或 skill name
                cmd = skill.slash_command if skill.slash_command else skill.name
                lines.append(f"  /{cmd} - {skill.description[:60]}...")
        lines.append("")
        lines.append("使用方式：输入 /skill-name 来激活对应的 skill")
        lines.append("例如：/search 搜索最新信息")
        return "\n".join(lines)
