"""兼容层。

新的抽象已经迁移到 short_term_memory / long_term_memory。
这里保留旧导入路径的转发。
"""

from agent_framework.memory.long_term_memory.base import LongTermMemoryStore
from agent_framework.memory.short_term_memory.base import ShortTermMemoryStore as SessionStore

__all__ = ["LongTermMemoryStore", "SessionStore"]
