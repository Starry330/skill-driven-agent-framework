"""memory 协调层。

MemoryManager 把 short-term memory、long-term memory 和摘要器组合成统一接口，
供 Gateway 和 workflow 节点使用。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from agent_framework.memory.flush import flush_to_memory
from agent_framework.memory.long_term_memory.base import LongTermMemoryStore
from agent_framework.memory.long_term_memory.retrievers.simple import SimpleLongTermMemoryRetriever
from agent_framework.memory.models import MemoryRecord, SessionRecord, SessionStateRecord
from agent_framework.memory.short_term_memory.base import ShortTermMemoryStore
from agent_framework.memory.short_term_memory.summarizer import Summarizer

logger = logging.getLogger(__name__)


class MemoryManager:
    """统一协调 short-term transcript/state 和 long-term memory。"""

    def __init__(
        self,
        short_term_store: ShortTermMemoryStore,
        long_term_store: LongTermMemoryStore,
        summarizer: Summarizer | None = None,
        settings: object | None = None,
    ) -> None:
        self.short_term_store = short_term_store
        self.long_term_store = long_term_store
        self.retriever = SimpleLongTermMemoryRetriever(long_term_store)
        self.summarizer = summarizer or Summarizer()
        self.settings = settings

    def ensure_session(self, session_id: str, agent_id: str, parent_session_id: str | None = None) -> None:
        self.short_term_store.create_session(
            SessionRecord(session_id=session_id, agent_id=agent_id, parent_session_id=parent_session_id)
        )

    def append_message(
        self,
        session_id: str,
        role: str,
        content: Any,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        self.short_term_store.append_message(session_id, role, content, tool_call_id=tool_call_id, name=name)

    def load_messages(self, session_id: str) -> List[BaseMessage]:
        return self.short_term_store.load_messages(session_id)

    def load_state(self, session_id: str) -> SessionStateRecord:
        return self.short_term_store.load_state(session_id)

    def save_state(self, state: SessionStateRecord) -> None:
        self.short_term_store.save_state(state)

    def log_event(self, session_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        self.short_term_store.log_event(session_id, event_type, payload)

    def retrieve(self, query: str, namespaces: List[str]) -> List[str]:
        return [record.content for record in self.retriever.search(query, namespaces)]

    def write_memory(self, namespace: str, content: str, metadata: Dict[str, Any] | None = None) -> None:
        self.long_term_store.store(
            MemoryRecord(
                namespace=namespace,
                key=str(uuid.uuid4()),
                content=content,
                metadata=metadata or {},
            )
        )

    def compact_if_needed(
        self,
        session_id: str,
        llm: BaseChatModel,
        messages: List[BaseMessage],
        max_history_messages: int,
        keep_last: int,
    ) -> str:
        # transcript 过长时只折叠旧消息，最近消息继续保留给本轮推理使用。
        if len(messages) <= max_history_messages:
            return self.load_state(session_id).summary
        summary_source = messages[:-keep_last] if keep_last > 0 else messages
        # 压缩前提取关键事实，防止信息丢失
        if self.settings is None or getattr(self.settings, "memory_flush_enabled", True):
            flush_to_memory(summary_source, self, llm)
        summary = self.summarizer.summarize(summary_source, llm)
        state = self.load_state(session_id)
        state.summary = summary
        self.save_state(state)
        return summary

    def reflect_and_store(
        self,
        session_id: str,
        agent_id: str,
        messages: List[BaseMessage],
        llm: BaseChatModel,
        summary: str = "",
    ) -> bool:
        """执行反思和经验提炼流程。

        Args:
            session_id: 会话ID
            agent_id: Agent ID
            messages: 对话消息列表
            llm: 语言模型
            summary: 任务摘要

        Returns:
            是否成功执行反思
        """
        # 检查是否启用反思
        if self.settings is not None and not getattr(self.settings, "memory_reflection_enabled", True):
            return False

        # 检查消息数量是否足够
        if len(messages) < 3:
            return False

        try:
            from agent_framework.memory.reflection.engine import ReflectionEngine
            from agent_framework.memory.reflection.distiller import ExperienceDistiller

            # 执行反思
            engine = ReflectionEngine(llm)
            reflection = engine.reflect(messages, summary)
            if reflection is None:
                return False

            # 提炼经验
            distiller = ExperienceDistiller(self.long_term_store)
            records = distiller.distill(reflection)

            # 存储经验
            for record in records:
                record.key = str(uuid.uuid4())
                self.long_term_store.store(record)

            # 记录反思日志
            self._log_reflection(session_id, agent_id, reflection)

            logger.info(
                "反思完成: session=%s, outcome=%s, procedures=%d, episodes=%d, preferences=%d",
                session_id,
                reflection.outcome,
                len(reflection.procedures),
                len(reflection.episodes),
                len(reflection.preferences),
            )
            return True

        except Exception:
            logger.exception("reflect_and_store: 反思流程失败")
            return False

    def _log_reflection(self, session_id: str, agent_id: str, reflection: object) -> None:
        """记录反思日志到数据库。"""
        try:
            import json
            from agent_framework.memory.sqlite_backend import SQLiteMemoryBackend

            backend = SQLiteMemoryBackend(getattr(self.settings, "database_path", "storage/runtime.db"))
            conn = backend.connect()
            try:
                conn.execute(
                    """INSERT INTO reflection_logs (session_id, agent_id, outcome, reflection_data)
                    VALUES (?, ?, ?, ?)""",
                    (
                        session_id,
                        agent_id,
                        getattr(reflection, "outcome", "unknown"),
                        json.dumps({
                            "outcome": getattr(reflection, "outcome", "unknown"),
                            "procedures_count": len(getattr(reflection, "procedures", [])),
                            "episodes_count": len(getattr(reflection, "episodes", [])),
                            "preferences_count": len(getattr(reflection, "preferences", [])),
                            "lessons_count": len(getattr(reflection, "lessons", [])),
                        }),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.debug("记录反思日志失败")
