from typing import Any, List, Dict, Optional

class LongTermMemory:
    """
    A simple in-memory implementation of long-term memory.
    """
    
    def __init__(self):
        # Structure: {namespace: {key: value}}
        self._storage: Dict[str, Dict[str, Any]] = {}

    def store(self, key: str, value: Any, namespace: str) -> None:
        """
        Store a value in the memory under a specific namespace and key.
        """
        if namespace not in self._storage:
            self._storage[namespace] = {}
        self._storage[namespace][key] = value

    def retrieve(self, key: str, namespace: str) -> Optional[Any]:
        """
        Retrieve a value from the memory by key and namespace.
        """
        if namespace in self._storage:
            return self._storage[namespace].get(key)
        return None

    def search(self, query: str, namespace: str) -> List[Any]:
        """
        Search for values in a namespace that match the query.
        For this simple implementation, we check if the query is in the key or string representation of the value.
        """
        results = []
        if namespace in self._storage:
            for key, value in self._storage[namespace].items():
                if query.lower() in key.lower() or query.lower() in str(value).lower():
                    results.append(value)
        return results
