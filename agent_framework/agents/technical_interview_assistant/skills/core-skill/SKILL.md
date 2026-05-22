---
name: core-skill
description: 模拟完整的技术面试流程，包括提问、追问和总结
triggers: []
required_tools: []
permissions: []
input_schema:
  type: object
output_schema:
  type: string
decision_logic:
- else: use_declared_tools
constraints: []
failure_modes: []
fallback_strategy: []
tool_policy: {}
subagent_allowed: false
dependencies: []
availability_checks: []
enabled: true
metadata: {}
---
Use declared tools to complete this capability. When available context is insufficient, explain the limitation and ask for the missing information.
