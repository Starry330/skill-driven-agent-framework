"""短期记忆使用的摘要器。"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage


class Summarizer:
    """在 transcript 过长时把旧消息压缩成 summary。"""

    def summarize(self, messages: list[BaseMessage], llm: BaseChatModel) -> str:
        if not messages:
            return ""
        prompt = HumanMessage(
            content=(
                "请把以下历史对话压缩成简洁摘要，保留目标、关键事实、工具结果、未完成事项。\n\n"
                + "\n".join(str(message.content) for message in messages)
            )
        )
        response = llm.invoke([prompt])
        return str(response.content)
