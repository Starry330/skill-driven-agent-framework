"""长期记忆的抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from agent_framework.memory.models import MemoryRecord


class LongTermMemoryStore(ABC):
    """负责 semantic、episodic、user memory 等长期持久化知识。"""

    @abstractmethod
    def store(self, memory: MemoryRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def retrieve(self, namespace: str, key: str) -> MemoryRecord | None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, namespaces: List[str]) -> List[MemoryRecord]:
        raise NotImplementedError
