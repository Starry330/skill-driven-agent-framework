from pathlib import Path
import unittest

from agent_framework.bootstrap import BootstrapInjector, BootstrapLoader
from agent_framework.config.settings import FrameworkSettings


class BootstrapLoaderTest(unittest.TestCase):
    def test_load_workspace_and_render_sections(self) -> None:
        workspace = Path("agent_framework/agents/research/workspace")
        settings = FrameworkSettings()
        loader = BootstrapLoader(settings)
        snapshot = loader.load_workspace(workspace)

        self.assertIn("AGENTS.md", snapshot.documents)
        self.assertTrue(snapshot.get("SOUL.md"))

        injector = BootstrapInjector()
        sections = injector.build_prompt_sections(
            snapshot=snapshot,
            active_skills=[],
            memory_hits=[],
            summary="",
        )
        rendered = injector.render_system_prompt(sections)
        self.assertIn("AGENTS.md", rendered)
        self.assertIn("SOUL.md", rendered)


if __name__ == "__main__":
    unittest.main()
