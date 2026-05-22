from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_framework.config.env import load_project_env
from agent_framework.config.settings import DEFAULT_MIMO_BASE_URL, get_settings


class EnvConfigTest(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_load_project_env_parses_dotenv_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".env").write_text(
                "\n".join(
                    [
                        "# comment",
                        "MIMO_API_KEY='tp-short-demo'",
                        'AGENT_FRAMEWORK_BUILDER_MODEL="mimo-v2.5-pro"',
                        "AGENT_FRAMEWORK_DEBUG=true",
                        "AGENT_FRAMEWORK_STORAGE_ROOT=custom_storage # inline comment",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                env = load_project_env(root)

        self.assertEqual(env["MIMO_API_KEY"], "tp-short-demo")
        self.assertEqual(env["AGENT_FRAMEWORK_BUILDER_MODEL"], "mimo-v2.5-pro")
        self.assertEqual(env["AGENT_FRAMEWORK_DEBUG"], "true")
        self.assertEqual(env["AGENT_FRAMEWORK_STORAGE_ROOT"], "custom_storage")

    def test_system_environment_overrides_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".env").write_text("MIMO_API_KEY=from-dotenv", encoding="utf-8")

            with patch.dict(os.environ, {"MIMO_API_KEY": "from-system"}, clear=True):
                env = load_project_env(root)

        self.assertEqual(env["MIMO_API_KEY"], "from-system")

    def test_settings_accept_generic_api_key_fallback(self) -> None:
        get_settings.cache_clear()
        with patch.dict(os.environ, {"API_KEY": "tp-short-demo"}, clear=True):
            settings = get_settings()

        self.assertEqual(settings.builder_llm.api_key, "tp-short-demo")
        self.assertEqual(settings.research_llm.api_key, "tp-short-demo")
        self.assertEqual(settings.fea_llm.api_key, "tp-short-demo")

    def test_settings_load_mimo_defaults_and_env_overrides(self) -> None:
        get_settings.cache_clear()
        with patch.dict(
            os.environ,
            {
                "MIMO_API_KEY": "tp-short-demo",
                "AGENT_FRAMEWORK_BUILDER_MODEL": "mimo-v2.5-pro",
                "AGENT_FRAMEWORK_BUILDER_TEMPERATURE": "0.1",
            },
            clear=True,
        ):
            settings = get_settings()

        self.assertEqual(settings.builder_llm.base_url, DEFAULT_MIMO_BASE_URL)
        self.assertEqual(settings.builder_llm.api_key, "tp-short-demo")
        self.assertEqual(settings.builder_llm.model, "mimo-v2.5-pro")
        self.assertEqual(settings.builder_llm.temperature, 0.1)

    def test_builder_llm_requires_api_key(self) -> None:
        get_settings.cache_clear()
        with patch.dict(
            os.environ,
            {
                "AGENT_FRAMEWORK_BUILDER_API_KEY": "",
                "MIMO_API_KEY": "",
                "API_KEY": "",
                "OPENAI_API_KEY": "",
            },
        ):
            from chat_with_builder_agent import build_llm

            with self.assertRaisesRegex(RuntimeError, "AGENT_FRAMEWORK_BUILDER_API_KEY"):
                build_llm()


if __name__ == "__main__":
    unittest.main()
