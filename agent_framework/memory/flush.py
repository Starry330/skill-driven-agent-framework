"""压缩前事实提取。

在摘要压缩之前，用 LLM 从即将被折叠的消息中提取关键事实，
写入长期记忆的 semantic namespace，防止压缩导致信息丢失。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage

logger = logging.getLogger(__name__)


def flush_to_memory(
    messages: List[BaseMessage],
    memory_manager: object,
    llm: BaseChatModel,
) -> None:
    """从即将被压缩的消息中提取关键事实，写入长期记忆。

    Args:
        messages: 即将被摘要折叠的消息列表。
        memory_manager: 拥有 write_memory(namespace,, content) 方法的 MemoryManager。
        llm: 用于提取事实的语言模型。
    """
    if not messages:
        return

    conversation = "\n".join(f"{msg.type}: {msg.content}" for msg in messages)
    prompt = HumanMessage(
        content=(
            "从以下对话中提取值得长期记住的关键事实。"
            "每个事实必须是独立、完整的陈述"
            "（如决策、约束、文件路径、参数值、用户偏好）。\n"
            "输出一个 JSON 字符串数组，只输出 JSON，不要其他内容。\n\n"
            + conversation
        )
    )

    try:
        response = llm.invoke([prompt])
    except Exception:
        logger.exception("flush_to_memory: LLM 调用失败")
        return

    json_str = str(response.content).strip()

    # 剥离 markdown code fence
    if "```json" in json_str:
        json_str = json_str.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        facts = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning("flush_to_memory: 无法解析 LLM 输出为 JSON: %s", json_str[:200])
        return

    if not isinstance(facts, list):
        return

    for fact in facts:
        if isinstance(fact, str) and fact.strip():
            metadata = {
                "source": "flush",
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "confidence": 0.6,
            }
            memory_manager.write_memory(namespace="semantic", content=fact.strip(), metadata=metadata)
