"""短期/长期记忆共用的 SQLite 底层连接与 schema。"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteMemoryBackend:
    """封装共享数据库连接与 schema，避免长短期记忆重复实现底层细节。"""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        conn = self.connect()
        try:
            # 短期会话记忆和长期记忆共享同一个 SQLite 文件，但表边界保持分离。
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    parent_session_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tool_call_id TEXT,
                    name TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS session_state (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL DEFAULT '',
                    active_skills TEXT NOT NULL DEFAULT '[]',
                    working_state TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS memories (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (namespace, key)
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS memory_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    keyword TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    UNIQUE(namespace, key, keyword)
                );
                CREATE INDEX IF NOT EXISTS idx_memory_keywords_keyword ON memory_keywords(keyword);
                CREATE TABLE IF NOT EXISTS reflection_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    reflection_data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            # 向后兼容：为已有 messages 表添加新列（如果不存在）
            cursor = conn.execute("PRAGMA table_info(messages)")
            existing_columns = {row["name"] for row in cursor.fetchall()}
            if "tool_call_id" not in existing_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN tool_call_id TEXT")
            if "name" not in existing_columns:
                conn.execute("ALTER TABLE messages ADD COLUMN name TEXT")
            # 向后兼容：为已有 memories 表添加新列（如果不存在）
            cursor = conn.execute("PRAGMA table_info(memories)")
            existing_columns = {row["name"] for row in cursor.fetchall()}
            if "experience_type" not in existing_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN experience_type TEXT DEFAULT ''")
            if "confidence" not in existing_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 0.5")
            if "usage_count" not in existing_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN usage_count INTEGER DEFAULT 0")
            if "last_used_at" not in existing_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN last_used_at TEXT")
            if "tags" not in existing_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN tags TEXT DEFAULT '[]'")
            if "task_pattern" not in existing_columns:
                conn.execute("ALTER TABLE memories ADD COLUMN task_pattern TEXT DEFAULT ''")
            conn.commit()
        finally:
            conn.close()
