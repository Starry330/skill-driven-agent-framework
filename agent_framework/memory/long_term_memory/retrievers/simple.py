"""长期记忆的简单检索器。"""

from __future__ import annotations

from typing import List

from agent_framework.memory.long_term_memory.base import LongTermMemoryStore
from agent_framework.memory.models import MemoryRecord


class SimpleLongTermMemoryRetriever:
    """当前默认使用简单 LIKE 检索，后续可替换为向量检索。"""

    def __init__(self, store: LongTermMemoryStore) -> None:
        self.store = store

    def search(self, query: str, namespaces: List[str]) -> List[MemoryRecord]:
        return self.store.search(query, namespaces)
