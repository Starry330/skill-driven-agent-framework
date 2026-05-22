"""兼容层。"""

from agent_framework.memory.long_term_memory.retrievers.simple import (
    SimpleLongTermMemoryRetriever as SimpleMemoryRetriever,
)

__all__ = ["SimpleMemoryRetriever"]
