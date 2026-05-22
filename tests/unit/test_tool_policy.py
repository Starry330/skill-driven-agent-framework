import unittest

from agent_framework.tools.adapters.local import build_local_tool_spec
from agent_framework.tools.basic import calculator
from agent_framework.tools.models import ToolExecutionContext
from agent_framework.tools.policy import ToolPolicy, ToolPolicyEngine


class ToolPolicyTest(unittest.TestCase):
    def test_requires_active_skill_rejects_tool_without_active_skill(self) -> None:
        policy = ToolPolicy(allowlist=["calculator"])
        context = ToolExecutionContext(
            agent_id="demo",
            session_id="session",
            requires_active_skill=True,
        )
        decision = ToolPolicyEngine().evaluate(
            build_local_tool_spec(calculator),
            context,
            policy,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "agent requires an active skill before tool use")


if __name__ == "__main__":
    unittest.main()
