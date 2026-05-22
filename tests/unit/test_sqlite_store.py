from pathlib import Path
import tempfile
import unittest

from langchain_core.messages import AIMessage, ToolMessage

from agent_framework.memory import MemoryRecord, SQLiteLongTermMemoryStore, SQLiteShortTermMemoryStore
from agent_framework.memory.models import SessionRecord, SessionStateRecord


class SQLiteStoreTest(unittest.TestCase):
    def test_session_and_memory_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "runtime.db"
            short_term_store = SQLiteShortTermMemoryStore(database_path)
            long_term_store = SQLiteLongTermMemoryStore(database_path)
            short_term_store.create_session(SessionRecord(session_id="s1", agent_id="research"))
            short_term_store.append_message("s1", "user", "hello")
            short_term_store.save_state(SessionStateRecord(session_id="s1", summary="summary"))
            long_term_store.store(MemoryRecord(namespace="semantic", key="k1", content="important note"))

            messages = short_term_store.load_messages("s1")
            state = short_term_store.load_state("s1")
            memories = long_term_store.search("important", ["semantic"])

            self.assertEqual(len(messages), 1)
            self.assertEqual(state.summary, "summary")
            self.assertEqual(len(memories), 1)

    def test_persisted_tool_messages_are_replayed_as_plain_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "runtime.db"
            short_term_store = SQLiteShortTermMemoryStore(database_path)
            short_term_store.create_session(SessionRecord(session_id="s2", agent_id="builder"))
            short_term_store.append_message("s2", "user", "hello")
            short_term_store.append_message("s2", "tool", '{"status":"ok"}')

            messages = short_term_store.load_messages("s2")

            self.assertEqual(len(messages), 2)
            self.assertIsInstance(messages[1], AIMessage)
            self.assertNotIsInstance(messages[1], ToolMessage)
            self.assertIn("历史工具执行结果", str(messages[1].content))


if __name__ == "__main__":
    unittest.main()
