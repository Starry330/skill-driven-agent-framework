"""test_memory_index.py — 记忆索引管理器单元测试。"""

import json
import tempfile
import unittest
from pathlib import Path

from agent_framework.memory.index.manager import MemoryIndexManager
from agent_framework.memory.models import MemoryRecord


class MemoryIndexManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = str(Path(self.temp_dir) / "test.db")
        self.manager = MemoryIndexManager(self.db_path)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_keywords(self) -> None:
        """测试关键词提取。"""
        content = "用户偏好中文交流，项目使用Python开发"
        keywords = self.manager.extract_keywords(content)
        self.assertIsInstance(keywords, list)
        self.assertTrue(len(keywords) > 0)
        # 应该包含中文关键词
        self.assertTrue(any("中文" in kw for kw in keywords))

    def test_extract_keywords_english(self) -> None:
        """测试英文关键词提取。"""
        content = "The user prefers dark theme for the project"
        keywords = self.manager.extract_keywords(content)
        self.assertIsInstance(keywords, list)
        self.assertTrue(len(keywords) > 0)
        # 应该包含英文关键词
        self.assertTrue(any("dark" in kw for kw in keywords))

    def test_store_keywords(self) -> None:
        """测试关键词存储。"""
        # 先创建表
        from agent_framework.memory.sqlite_backend import SQLiteMemoryBackend
        backend = SQLiteMemoryBackend(self.db_path)

        keywords = ["中文", "交流", "偏好"]
        self.manager.store_keywords("test_namespace", "test_key", keywords)

        # 验证关键词已存储
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT keyword FROM memory_keywords WHERE namespace = ? AND key = ?",
            ("test_namespace", "test_key"),
        ).fetchall()
        conn.close()

        stored_keywords = [row[0] for row in rows]
        self.assertEqual(set(stored_keywords), set(keywords))

    def test_search_with_score(self) -> None:
        """测试评分检索。"""
        # 创建测试数据库
        from agent_framework.memory.sqlite_backend import SQLiteMemoryBackend
        backend = SQLiteMemoryBackend(self.db_path)

        # 存储测试记忆
        conn = backend.connect()
        try:
            conn.execute(
                """INSERT INTO memories (namespace, key, content, metadata, experience_type, confidence)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ("procedures", "test1", "创建Agent的步骤：1.收集需求 2.设计蓝图", "{}", "procedure", 0.8),
            )
            conn.execute(
                """INSERT INTO memory_keywords (namespace, key, keyword, weight)
                VALUES (?, ?, ?, ?)""",
                ("procedures", "test1", "创建", 1.0),
            )
            conn.execute(
                """INSERT INTO memory_keywords (namespace, key, keyword, weight)
                VALUES (?, ?, ?, ?)""",
                ("procedures", "test1", "Agent", 1.0),
            )
            conn.commit()
        finally:
            conn.close()

        # 检索
        results = self.manager.search_with_score("创建Agent", ["procedures"], top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].key, "test1")

    def test_calculate_recency(self) -> None:
        """测试时间衰减计算。"""
        from datetime import datetime, timezone, timedelta

        # 测试当前时间
        now = datetime.now(timezone.utc).isoformat()
        score = self.manager._calculate_recency(now)
        self.assertGreater(score, 0.9)  # 应该接近1.0

        # 测试30天前的时间
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        score = self.manager._calculate_recency(thirty_days_ago)
        self.assertLess(score, 0.6)  # 应该有明显衰减

    def test_update_usage_stats(self) -> None:
        """测试使用统计更新。"""
        # 创建测试记忆
        from agent_framework.memory.sqlite_backend import SQLiteMemoryBackend
        backend = SQLiteMemoryBackend(self.db_path)

        conn = backend.connect()
        try:
            conn.execute(
                """INSERT INTO memories (namespace, key, content, metadata, usage_count)
                VALUES (?, ?, ?, ?, ?)""",
                ("test", "key1", "content", "{}", 0),
            )
            conn.commit()
        finally:
            conn.close()

        # 更新使用统计
        self.manager.update_usage_stats("test", "key1")

        # 验证更新
        conn = backend.connect()
        try:
            row = conn.execute(
                "SELECT usage_count FROM memories WHERE namespace = ? AND key = ?",
                ("test", "key1"),
            ).fetchone()
            self.assertEqual(row[0], 1)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
