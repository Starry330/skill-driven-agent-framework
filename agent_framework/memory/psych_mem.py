import uuid
from datetime import datetime
from typing import List
from .long_term import LongTermMemory

class PsychMem:
    """
    Cognitive Alignment Memory System (PsychMem).
    Wraps LongTermMemory to manage episodic and semantic memories.
    """
    
    def __init__(self, memory: LongTermMemory):
        self.memory = memory
        self.episodic_namespace = "episodic"
        self.semantic_namespace = "semantic"

    def add_episodic(self, content: str) -> None:
        """
        Adds ephemeral memory (simulated decay by timestamp).
        """
        key = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        value = {
            "content": content,
            "timestamp": timestamp,
            "type": "episodic"
        }
        self.memory.store(key, value, self.episodic_namespace)

    def add_semantic(self, content: str) -> None:
        """
        Adds permanent memory.
        """
        key = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        value = {
            "content": content,
            "timestamp": timestamp,
            "type": "semantic"
        }
        self.memory.store(key, value, self.semantic_namespace)

    def retrieve_relevant(self, context: str) -> str:
        """
        Retrieves combined memories relevant to the context.
        """
        episodic_results = self.memory.search(context, self.episodic_namespace)
        semantic_results = self.memory.search(context, self.semantic_namespace)
        
        # Combine results
        combined_results = episodic_results + semantic_results
        
        if not combined_results:
            return ""
            
        # Format results into a string
        formatted_memories = []
        for item in combined_results:
            formatted_memories.append(f"[{item['type'].upper()}] {item['content']} (Time: {item['timestamp']})")
            
        return "\n".join(formatted_memories)
