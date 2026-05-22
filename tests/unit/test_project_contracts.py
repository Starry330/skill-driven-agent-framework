from pathlib import Path
import re
import unittest

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent_framework.agents import create_builder_agent
from agent_framework.config.settings import FrameworkSettings


class StaticChatModel(FakeListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):  # type: ignore[override]
        return self


class ProjectContractTest(unittest.TestCase):
    def test_builder_workspace_tools_match_registered_tools(self) -> None:
        settings = FrameworkSettings(workspace_root=Path.cwd())
        spec, tools = create_builder_agent(StaticChatModel(responses=["ok"]), settings)
        documented = {
            match.group(1)
            for match in re.finditer(
                r"- `([^`]+)`",
                Path("agent_framework/agents/builder/workspace/TOOLS.md").read_text(encoding="utf-8"),
            )
        }
        registered = {tool.name for tool in tools}

        self.assertEqual(spec.agent_id, "builder")
        self.assertTrue(documented)
        self.assertEqual(documented, registered)

    def test_repository_does_not_contain_hardcoded_api_keys(self) -> None:
        pattern = re.compile(r"(?:sk|tp)-[A-Za-z0-9_\-]{20,}")
        for path in Path(".").rglob("*.py"):
            if ".venv" in path.parts:
                continue
            content = path.read_text(encoding="utf-8")
            self.assertIsNone(pattern.search(content), msg=f"hardcoded api key found in {path}")

    def test_documented_chat_entrypoints_exist(self) -> None:
        docs = [
            Path("README.md").read_text(encoding="utf-8"),
            Path("USAGE_GUIDE.md").read_text(encoding="utf-8"),
            Path("BUILDER_GUIDE.md").read_text(encoding="utf-8"),
        ]
        documented_scripts = {
            match.group(0)
            for doc in docs
            for match in re.finditer(r"chat_with_[a-z_]+\.py", doc)
        }
        self.assertTrue(documented_scripts)
        for script_name in documented_scripts:
            self.assertTrue(Path(script_name).exists(), msg=f"missing documented script: {script_name}")


if __name__ == "__main__":
    unittest.main()
