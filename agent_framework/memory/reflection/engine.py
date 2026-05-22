"""反思引擎：分析执行轨迹，提取结构化洞察。"""

from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, ToolMessage

from agent_framework.memory.models import (
    EpisodicExperience,
    ProceduralExperience,
    ReflectionResult,
    UserPreference,
)
from agent_framework.memory.reflection.prompts import build_reflection_prompt

logger = logging.getLogger(__name__)


class ReflectionEngine:
    """分析执行轨迹，提取结构化洞察。"""

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    def reflect(
        self,
        messages: List[BaseMessage],
        summary: str = "",
    ) -> ReflectionResult | None:
        """分析对话执行轨迹，提取反思结果。

        Args:
            messages: 对话消息列表
            summary: 任务摘要

        Returns:
            ReflectionResult 或 None（如果分析失败）
        """
        if len(messages) < 3:
            return None

        conversation = self._format_conversation(messages)
        tool_results = self._extract_tool_results(messages)

        prompt = build_reflection_prompt(conversation, tool_results, summary)

        try:
            response = self.llm.invoke([prompt])
        except Exception:
            logger.exception("ReflectionEngine: LLM调用失败")
            return None

        return self._parse_response(str(response.content))

    def _format_conversation(self, messages: List[BaseMessage]) -> str:
        """格式化对话为可读文本。"""
        lines = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                lines.append(f"tool_result: {msg.content[:500]}")
            else:
                role = msg.type if hasattr(msg, "type") else "unknown"
                content = str(msg.content)[:500] if msg.content else ""
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _extract_tool_results(self, messages: List[BaseMessage]) -> str:
        """提取工具调用结果。"""
        tool_results = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                tool_results.append(str(msg.content)[:300])
        return "\n".join(tool_results) if tool_results else "无工具调用"

    def _parse_response(self, response_text: str) -> ReflectionResult | None:
        """解析LLM响应为ReflectionResult。"""
        json_str = response_text.strip()

        # 剥离markdown code fence
        if "```json" in json_str:
            json_str = json_str.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            data = json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            logger.warning("ReflectionEngine: 无法解析LLM输出为JSON: %s", json_str[:200])
            return None

        if not isinstance(data, dict):
            return None

        try:
            outcome = data.get("outcome", "partial")
            if outcome not in ("success", "partial", "failure"):
                outcome = "partial"

            procedures = []
            for p in data.get("procedures", []):
                if isinstance(p, dict):
                    procedures.append(
                        ProceduralExperience(
                            task_pattern=p.get("task_pattern", ""),
                            steps=p.get("steps", []),
                            content=p.get("content", ""),
                            confidence=float(p.get("confidence", 0.5)),
                        )
                    )

            episodes = []
            for e in data.get("episodes", []):
                if isinstance(e, dict):
                    episodes.append(
                        EpisodicExperience(
                            context_summary=e.get("context_summary", ""),
                            outcome=e.get("outcome", "partial"),
                            key_factors=e.get("key_factors", []),
                            content=e.get("content", ""),
                            confidence=float(e.get("confidence", 0.5)),
                        )
                    )

            preferences = []
            for pref in data.get("preferences", []):
                if isinstance(pref, dict):
                    preferences.append(
                        UserPreference(
                            category=pref.get("category", ""),
                            content=pref.get("content", ""),
                            evidence=pref.get("evidence", []),
                            confidence=float(pref.get("confidence", 0.5)),
                        )
                    )

            lessons = data.get("lessons", [])
            if not isinstance(lessons, list):
                lessons = []

            return ReflectionResult(
                outcome=outcome,
                procedures=procedures,
                episodes=episodes,
                preferences=preferences,
                lessons=lessons,
            )
        except (ValueError, TypeError) as e:
            logger.warning("ReflectionEngine: 解析反思结果失败: %s", e)
            return None
