from pathlib import Path
import unittest

from agent_framework.skills.loader import SkillLoader


class SkillMarkdownConventionTest(unittest.TestCase):
    def test_all_skill_names_use_kebab_case(self) -> None:
        skill_files = list(Path("agent_framework").rglob("SKILL.md"))
        self.assertTrue(skill_files)
        for skill_file in skill_files:
            content = skill_file.read_text(encoding="utf-8")
            name_lines = [line for line in content.splitlines()[:12] if line.startswith("name:")]
            self.assertEqual(len(name_lines), 1, msg=f"missing name in {skill_file}")
            self.assertNotIn("_", name_lines[0], msg=f"skill name should use kebab-case: {skill_file}")

    def test_builder_skills_pass_protocol_validation(self) -> None:
        loader = SkillLoader()
        skill_files = list(Path("agent_framework/agents/builder/skills").rglob("SKILL.md"))
        self.assertGreaterEqual(len(skill_files), 11)
        for skill_file in skill_files:
            spec = loader.load(skill_file)
            self.assertEqual(spec.metadata.get("category"), "builder")
            self.assertTrue(spec.decision_logic)
            self.assertTrue(spec.constraints)
            self.assertTrue(spec.failure_modes)
            self.assertTrue(spec.fallback_strategy)
            self.assertTrue(spec.tool_policy)
            self.assertEqual(skill_file.parent.name, spec.name)


if __name__ == "__main__":
    unittest.main()
