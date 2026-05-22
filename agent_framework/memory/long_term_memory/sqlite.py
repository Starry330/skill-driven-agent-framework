"""长期记忆的 SQLite 持久化实现。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from agent_framework.memory.long_term_memory.base import LongTermMemoryStore
from agent_framework.memory.models import MemoryRecord
from agent_framework.memory.sqlite_backend import SQLiteMemoryBackend


class SQLiteLongTermMemoryStore(LongTermMemoryStore):
    """基于 SQLite 的长期记忆实现。"""

    def __init__(self, database_path: str | Path) -> None:
        self.backend = SQLiteMemoryBackend(database_path)

    def store(self, memory: MemoryRecord) -> None:
        conn = self.backend.connect()
        try:
            conn.execute(
                """
                INSERT INTO memories (namespace, key, content, metadata)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    content = excluded.content,
                    metadata = excluded.metadata
                """,
                (memory.namespace, memory.key, memory.content, json.dumps(memory.metadata, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

    def store_with_keywords(self, memory: MemoryRecord, keywords: List[str]) -> None:
        """存储记忆并更新关键词索引。"""
        conn = self.backend.connect()
        try:
            # 存储记忆
            conn.execute(
                """
                INSERT INTO memories (namespace, key, content, metadata, experience_type,
                    confidence, usage_count, last_used_at, tags, task_pattern)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, key) DO UPDATE SET
                    content = excluded.content,
                    metadata = excluded.metadata,
                    experience_type = excluded.experience_type,
                    confidence = excluded.confidence,
                    usage_count = excluded.usage_count,
                    last_used_at = excluded.last_used_at,
                    tags = excluded.tags,
                    task_pattern = excluded.task_pattern
                """,
                (
                    memory.namespace,
                    memory.key,
                    memory.content,
                    json.dumps(memory.metadata, ensure_ascii=False),
                    memory.experience_type,
                    memory.confidence,
                    memory.usage_count,
                    memory.last_used_at,
                    json.dumps(memory.tags),
                    memory.task_pattern,
                ),
            )

            # 存储关键词索引
            for keyword in keywords:
                conn.execute(
                    """INSERT OR REPLACE INTO memory_keywords (namespace, key, keyword, weight)
                    VALUES (?, ?, ?, 1.0)""",
                    (memory.namespace, memory.key, keyword),
                )

            conn.commit()
        finally:
            conn.close()

    def retrieve(self, namespace: str, key: str) -> MemoryRecord | None:
        conn = self.backend.connect()
        try:
            row = conn.execute(
                "SELECT namespace, key, content, metadata FROM memories WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return MemoryRecord(
            namespace=row["namespace"],
            key=row["key"],
            content=row["content"],
            metadata=json.loads(row["metadata"]),
        )

    def search(self, query: str, namespaces: List[str]) -> List[MemoryRecord]:
        if not namespaces:
            return []
        placeholders = ",".join("?" for _ in namespaces)
        sql = f"""
            SELECT namespace, key, content, metadata
            FROM memories
            WHERE namespace IN ({placeholders}) AND content LIKE ?
            ORDER BY created_at DESC
            LIMIT 10
        """
        conn = self.backend.connect()
        try:
            rows = conn.execute(sql, (*namespaces, f"%{query}%")).fetchall()
        finally:
            conn.close()
        return [
            MemoryRecord(
                namespace=row["namespace"],
                key=row["key"],
                content=row["content"],
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]

    def search_with_score(
        self,
        query: str,
        namespaces: List[str],
        top_k: int = 10,
    ) -> List[MemoryRecord]:
        """使用关键词索引进行评分检索。"""
        if not namespaces:
            return []

        # 简单的关键词提取
        import re
        keywords = re.findall(r"[a-zA-Z_]+|[一-鿿]+", query.lower())
        keywords = [kw for kw in keywords if len(kw) >= 2][:10]

        if not keywords:
            return self.search(query, namespaces)

        conn = self.backend.connect()
        conn.row_factory = None
        try:
            placeholders = ",".join("?" for _ in namespaces)
            keyword_placeholders = ",".join("?" for _ in keywords)

            sql = f"""
                SELECT DISTINCT
                    m.namespace, m.key, m.content, m.metadata,
                    m.experience_type, m.confidence, m.usage_count,
                    m.last_used_at, m.tags, m.task_pattern, m.created_at,
                    COUNT(mk.keyword) as keyword_matches
                FROM memories m
                LEFT JOIN memory_keywords mk ON m.namespace = mk.namespace AND m.key = mk.key
                WHERE m.namespace IN ({placeholders})
                    AND mk.keyword IN ({keyword_placeholders})
                GROUP BY m.namespace, m.key
                ORDER BY keyword_matches DESC, m.created_at DESC
                LIMIT ?
            """

            params = (*namespaces, *keywords, top_k)
            rows = conn.execute(sql, params).fetchall()

            records = []
            for row in rows:
                record = MemoryRecord(
                    namespace=row[0],
                    key=row[1],
                    content=row[2],
                    metadata=json.loads(row[3]) if row[3] else {},
                    experience_type=row[4] or "",
                    confidence=row[5] or 0.5,
                    usage_count=row[6] or 0,
                    last_used_at=row[7],
                    tags=json.loads(row[8]) if row[8] else [],
                    task_pattern=row[9] or "",
                )
                records.append(record)

            return records

        finally:
            conn.close()

    def update_memory_stats(self, namespace: str, key: str) -> None:
        """更新使用统计。"""
        conn = self.backend.connect()
        try:
            conn.execute(
                """UPDATE memories
                SET usage_count = usage_count + 1,
                    last_used_at = ?
                WHERE namespace = ? AND key = ?""",
                (datetime.now(timezone.utc).isoformat(), namespace, key),
            )
            conn.commit()
        finally:
            conn.close()
