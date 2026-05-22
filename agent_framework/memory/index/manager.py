"""记忆索引管理器：关键词提取、索引更新、评分检索。"""

from __future__ import annotations

import logging
import math
import re
import sqlite3
from datetime import datetime, timezone
from typing import List, Set

from agent_framework.memory.models import MemoryRecord

logger = logging.getLogger(__name__)


class MemoryIndexManager:
    """记忆索引管理器：关键词提取、索引更新、评分检索。"""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path

    def extract_keywords(self, content: str) -> List[str]:
        """从内容中提取关键词。"""
        # 简单的关键词提取：分词、去停用词、去重
        stop_words = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "need", "dare", "ought",
            "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above", "below",
            "between", "out", "off", "over", "under", "again", "further", "then",
            "once", "here", "there", "when", "where", "why", "how", "all", "both",
            "each", "few", "more", "most", "other", "some", "such", "no", "nor",
            "not", "only", "own", "same", "so", "than", "too", "very", "s", "t",
            "just", "don", "now",
        }

        # 分词：中文按字符，英文按空格
        tokens = []
        # 英文单词
        english_words = re.findall(r"[a-zA-Z_]+", content.lower())
        tokens.extend(english_words)
        # 中文字符（连续2-4个字符作为关键词）
        chinese_chars = re.findall(r"[一-鿿]+", content)
        for chars in chinese_chars:
            if len(chars) >= 2:
                tokens.append(chars)

        # 去停用词和短词
        keywords = [t for t in tokens if t not in stop_words and len(t) >= 2]

        # 去重并限制数量
        seen: Set[str] = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
                if len(unique_keywords) >= 20:
                    break

        return unique_keywords

    def store_keywords(self, namespace: str, key: str, keywords: List[str]) -> None:
        """存储关键词索引。"""
        conn = sqlite3.connect(self.database_path)
        try:
            for keyword in keywords:
                conn.execute(
                    """INSERT OR REPLACE INTO memory_keywords (namespace, key, keyword, weight)
                    VALUES (?, ?, ?, 1.0)""",
                    (namespace, key, keyword),
                )
            conn.commit()
        finally:
            conn.close()

    def search_with_score(
        self,
        query: str,
        namespaces: List[str],
        top_k: int = 10,
    ) -> List[MemoryRecord]:
        """使用关键词索引进行评分检索。"""
        if not namespaces:
            return []

        query_keywords = self.extract_keywords(query)
        if not query_keywords:
            return []

        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            # 查找匹配关键词的记忆
            placeholders = ",".join("?" * len(namespaces))
            keyword_placeholders = ",".join("?" * len(query_keywords))

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

            params = (*namespaces, *query_keywords, top_k)
            rows = conn.execute(sql, params).fetchall()

            records = []
            for row in rows:
                # 计算评分
                keyword_matches = row["keyword_matches"]
                confidence = row["confidence"] or 0.5
                usage_count = row["usage_count"] or 0
                created_at = row["created_at"]

                # 时间衰减
                recency_score = self._calculate_recency(created_at)

                # 综合评分
                score = (
                    keyword_matches
                    * confidence
                    * recency_score
                    * (1 + math.log(1 + usage_count))
                )

                record = MemoryRecord(
                    namespace=row["namespace"],
                    key=row["key"],
                    content=row["content"],
                    metadata=__import__("json").loads(row["metadata"]) if row["metadata"] else {},
                    experience_type=row["experience_type"] or "",
                    confidence=confidence,
                    usage_count=usage_count,
                    last_used_at=row["last_used_at"],
                    tags=__import__("json").loads(row["tags"]) if row["tags"] else [],
                    task_pattern=row["task_pattern"] or "",
                )
                records.append((score, record))

            # 按评分排序
            records.sort(key=lambda x: x[0], reverse=True)
            return [record for _, record in records]

        finally:
            conn.close()

    def _calculate_recency(self, created_at: str | None) -> float:
        """计算时间衰减分数。"""
        if not created_at:
            return 0.5

        try:
            # 解析时间戳
            if "T" in created_at:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            else:
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone.utc)

            # 计算天数差
            now = datetime.now(timezone.utc)
            days_diff = (now - dt).total_seconds() / 86400

            # 指数衰减，半衰期30天
            half_life = 30
            return math.exp(-0.693 * days_diff / half_life)

        except (ValueError, TypeError):
            return 0.5

    def update_usage_stats(self, namespace: str, key: str) -> None:
        """更新使用统计。"""
        conn = sqlite3.connect(self.database_path)
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

    def store_memory_with_keywords(self, record: MemoryRecord) -> None:
        """存储记忆并更新关键词索引。"""
        # 提取关键词
        keywords = self.extract_keywords(record.content)

        # 存储记忆
        import json
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO memories
                (namespace, key, content, metadata, experience_type, confidence,
                 usage_count, last_used_at, tags, task_pattern)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.namespace,
                    record.key,
                    record.content,
                    json.dumps(record.metadata),
                    record.experience_type,
                    record.confidence,
                    record.usage_count,
                    record.last_used_at,
                    json.dumps(record.tags),
                    record.task_pattern,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        # 存储关键词索引
        self.store_keywords(record.namespace, record.key, keywords)
