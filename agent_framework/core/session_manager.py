"""会话层薄封装。

SessionManager 不直接持有数据库细节，只负责把 Gateway 的会话语义翻译成
 MemoryManager 能理解的读写操作，避免控制层直接碰底层存储接口。
"""

from __future__ import annotations

from typing import Optional

from langchain_core.messages import BaseMessage

from agent_framework.memory.manager import MemoryManager
from agent_framework.memory.models import SessionStateRecord


class SessionManager:
    """负责 session transcript 与 session state 的基本读写。"""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager

    def open(self, session_id: str, agent_id: str, parent_session_id: str | None = None) -> None:
        self.memory_manager.ensure_session(session_id, agent_id, parent_session_id)

    def append_user_message(self, session_id: str, content: str) -> None:
        self.memory_manager.append_message(session_id, "user", content)

    def append_assistant_message(self, session_id: str, content: str) -> None:
        self.memory_manager.append_message(session_id, "assistant", content)

    def append_tool_message(
        self,
        session_id: str,
        content: str,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        self.memory_manager.append_message(session_id, "tool", content, tool_call_id=tool_call_id, name=name)

    def load_messages(self, session_id: str) -> list[BaseMessage]:
        return self.memory_manager.load_messages(session_id)

    def load_state(self, session_id: str) -> SessionStateRecord:
        return self.memory_manager.load_state(session_id)

    def save_state(self, state: SessionStateRecord) -> None:
        self.memory_manager.save_state(state)
