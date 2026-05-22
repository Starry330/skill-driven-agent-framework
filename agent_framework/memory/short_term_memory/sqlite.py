"""短期会话记忆的 SQLite 持久化实现。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from agent_framework.memory.models import SessionRecord, SessionStateRecord
from agent_framework.memory.short_term_memory.base import ShortTermMemoryStore
from agent_framework.memory.sqlite_backend import SQLiteMemoryBackend


def _role_to_message(
    role: str,
    content: Any,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
) -> BaseMessage:
    """把持久化层的 role 恢复成 LangChain message。"""

    if role == "assistant":
        return AIMessage(content=content)
    if role == "tool":
        # 优先使用保存的 tool_call_id 和 name 重建完整的 ToolMessage
        if tool_call_id and name:
            return ToolMessage(content=content, tool_call_id=tool_call_id, name=name)
        # 向后兼容：旧数据没有 tool_call_id 和 name
        return AIMessage(content=f"历史工具执行结果：{content}")
    return HumanMessage(content=content)


class SQLiteShortTermMemoryStore(ShortTermMemoryStore):
    """基于 SQLite 的短期会话记忆实现。"""

    def __init__(self, database_path: str | Path) -> None:
        self.backend = SQLiteMemoryBackend(database_path)

    def ensure_schema(self) -> None:
        self.backend.ensure_schema()

    def create_session(self, record: SessionRecord) -> None:
        conn = self.backend.connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, agent_id, status, parent_session_id)
                VALUES (?, ?, ?, ?)
                """,
                (record.session_id, record.agent_id, record.status, record.parent_session_id),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO session_state (session_id, summary, active_skills, working_state)
                VALUES (?, '', '[]', '{}')
                """,
                (record.session_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_session(self, session_id: str) -> SessionRecord | None:
        conn = self.backend.connect()
        try:
            row = conn.execute(
                "SELECT session_id, agent_id, status, parent_session_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return SessionRecord(
            session_id=row["session_id"],
            agent_id=row["agent_id"],
            status=row["status"],
            parent_session_id=row["parent_session_id"],
        )

    def append_message(
        self,
        session_id: str,
        role: str,
        content: Any,
        tool_call_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        serialized = json.dumps(content, ensure_ascii=False) if not isinstance(content, str) else content
        conn = self.backend.connect()
        try:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, tool_call_id, name) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, serialized, tool_call_id, name),
            )
            conn.commit()
        finally:
            conn.close()

    def load_messages(self, session_id: str) -> List[BaseMessage]:
        conn = self.backend.connect()
        try:
            rows = conn.execute(
                "SELECT role, content, tool_call_id, name FROM messages WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        finally:
            conn.close()
        messages: List[BaseMessage] = []
        for row in rows:
            raw_content = row["content"]
            try:
                content = json.loads(raw_content)
            except json.JSONDecodeError:
                content = raw_content
            messages.append(
                _role_to_message(
                    row["role"],
                    content,
                    tool_call_id=row["tool_call_id"],
                    name=row["name"],
                )
            )
        return messages

    def load_state(self, session_id: str) -> SessionStateRecord:
        conn = self.backend.connect()
        try:
            row = conn.execute(
                "SELECT summary, active_skills, working_state FROM session_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return SessionStateRecord(session_id=session_id)
        return SessionStateRecord(
            session_id=session_id,
            summary=row["summary"],
            active_skills=json.loads(row["active_skills"]),
            working_state=json.loads(row["working_state"]),
        )

    def save_state(self, state: SessionStateRecord) -> None:
        conn = self.backend.connect()
        try:
            conn.execute(
                """
                INSERT INTO session_state (session_id, summary, active_skills, working_state)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    summary = excluded.summary,
                    active_skills = excluded.active_skills,
                    working_state = excluded.working_state
                """,
                (
                    state.session_id,
                    state.summary,
                    json.dumps(state.active_skills, ensure_ascii=False),
                    json.dumps(state.working_state, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def log_event(self, session_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        conn = self.backend.connect()
        try:
            conn.execute(
                "INSERT INTO events (session_id, event_type, payload) VALUES (?, ?, ?)",
                (session_id, event_type, json.dumps(payload, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()
