"""兼容层。

新的 SQLite 实现已经拆分为 short-term 和 long-term 两个类。
这里保留旧导入路径，避免已有代码立即失效。
"""

from agent_framework.memory.long_term_memory.sqlite import SQLiteLongTermMemoryStore
from agent_framework.memory.short_term_memory.sqlite import SQLiteShortTermMemoryStore

SQLiteSessionStore = SQLiteShortTermMemoryStore

__all__ = ["SQLiteLongTermMemoryStore", "SQLiteSessionStore", "SQLiteShortTermMemoryStore"]
