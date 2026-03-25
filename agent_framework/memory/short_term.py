from langgraph.checkpoint.memory import MemorySaver

def get_checkpointer() -> MemorySaver:
    """
    Returns a MemorySaver instance for short-term memory.
    This is an in-memory implementation for the MVP.
    """
    return MemorySaver()
