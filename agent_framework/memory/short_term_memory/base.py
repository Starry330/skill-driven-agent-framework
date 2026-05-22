"""短期会话记忆的抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from agent_framework.memory.models import SessionRecord, SessionStateRecord


class ShortTermMemoryStore(ABC):
    """负责 session transcript、summary、working_state 和事件日志。"""

    @abstractmethod
    def ensure_schema(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_session(self, record: SessionRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str) -> SessionRecord | None:
        raise NotImplementedError

    @abstractmethod
    def append_message(
        self,
        session_id: str,
        role: str,
        content: Any,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_messages(self, session_id: str) -> List[BaseMessage]:
        raise NotImplementedError

    @abstractmethod
    def load_state(self, session_id: str) -> SessionStateRecord:
        raise NotImplementedError

    @abstractmethod
    def save_state(self, state: SessionStateRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def log_event(self, session_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        raise NotImplementedError
