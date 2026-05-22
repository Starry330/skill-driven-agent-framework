import unittest

from agent_framework.skills import SkillRegistry, SkillRouter


class SkillRouterTest(unittest.TestCase):
    def test_web_search_skill_routes_for_search_query(self) -> None:
        registry = SkillRegistry()
        registry.load_directory("agent_framework/agents/research/skills")
        router = SkillRouter()
        routed = router.route("请帮我搜索一下这个问题", registry.enabled())
        self.assertTrue(routed)
        self.assertEqual(routed[0].name, "web-search")


if __name__ == "__main__":
    unittest.main()
