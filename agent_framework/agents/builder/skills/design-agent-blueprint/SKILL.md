---
name: design-agent-blueprint
description: Transform structured user requirements into a complete, normalized, and reviewable AgentBlueprint, then save it as the current pending blueprint for confirmation. This skill designs the agent blueprint only and must not create repository files or perform scaffold generation.
triggers:
  - 蓝图
  - blueprint
  - 设计agent
  - 规划agent
  - 创建agent
  - 设计智能体
required_tools:
  - save_pending_blueprint
permissions: []
input_schema:
  type: object
  required:
    - requirements
  properties:
    requirements:
      type: object
      description: 来自 collect_agent_requirements 的结构化需求对象。
      properties:
        agent_name:
          type: string
        agent_id:
          type: string
        role:
          type: string
        goal:
          type: string
        style_constraints:
          type: array
          items:
            type: string
        required_skills:
          type: array
          items:
            type: string
        required_tools:
          type: array
          items:
            type: string
        user_constraints:
          type: array
          items:
            type: string
        memory_requirements:
          type: array
          items:
            type: string
        workflow_preferences:
          type: array
          items:
            type: string
    existing_pending_blueprint:
      type: object
      description: 当前会话里已存在的 pending blueprint，可用于增量修订或局部覆盖。
    template_hint:
      type: string
      description: 可选的模板偏好，例如 research_agent、fea_agent、rag_agent。
output_schema:
  type: object
  required:
    - status
    - blueprint
    - missing_fields
    - conflicts
    - blueprint_summary
    - next_action
  properties:
    status:
      type: string
      enum:
        - need_more_info
        - conflict_detected
        - draft_blueprint
    blueprint:
      type: object
      description: 标准化后的 AgentBlueprint，可直接进入确认阶段。
      properties:
        agent_id:
          type: string
        name:
          type: string
        role:
          type: string
        goal:
          type: string
        style_constraints:
          type: array
          items:
            type: string
        workspace_docs:
          type: array
          items:
            type: object
            properties:
              name:
                type: string
              purpose:
                type: string
              required:
                type: boolean
        skills:
          type: array
          items:
            type: object
            properties:
              skill_name:
                type: string
              purpose:
                type: string
              triggers:
                type: array
                items:
                  type: string
              inputs:
                type: array
                items:
                  type: string
              outputs:
                type: array
                items:
                  type: string
        tool_plan:
          type: object
          properties:
            reuse_tools:
              type: array
              items:
                type: object
                properties:
                  tool_name:
                    type: string
                  purpose:
                    type: string
            new_tools:
              type: array
              items:
                type: object
                properties:
                  tool_name:
                    type: string
                  purpose:
                    type: string
                  reason:
                    type: string
                  io_schema:
                    type: object
                  implementation_hint:
                    type: string
                  risk_level:
                    type: string
                    enum:
                      - low
                      - medium
                      - high
        tool_policy:
          type: object
          properties:
            allow_existing_tools:
              type: boolean
            allow_local_tools:
              type: boolean
            allow_remote_mcp:
              type: boolean
            require_approval_for_repo_write:
              type: boolean
            require_audit_logging:
              type: boolean
        memory_namespaces:
          type: array
          items:
            type: string
        workflow_name:
          type: string
        create_chat_entry:
          type: boolean
        export_agent_factory:
          type: boolean
        confirmation_required:
          type: boolean
    missing_fields:
      type: array
      description: 仍然缺失、无法稳定生成 blueprint 的关键字段。
      items:
        type: string
    conflicts:
      type: array
      description: 当前需求中检测到的冲突项。
      items:
        type: string
    blueprint_summary:
      type: string
      description: 面向用户确认的简明蓝图摘要。
    next_action:
      type: string
      enum:
        - ask_user_for_missing_info
        - ask_user_to_resolve_conflict
        - wait_for_user_confirmation
decision_logic:
  - if: requirements 缺少 role、goal、skills 或关键约束，无法形成稳定蓝图
    return: need_more_info
  - if: requirements 中存在明显冲突，例如工具限制与能力目标互相矛盾
    return: conflict_detected
  - if: 信息完整且蓝图内部一致
    return: draft_blueprint
constraints:
  - 必须输出结构化、完整且可确认的 blueprint，不得返回松散自然语言替代结构化对象。
  - 不得省略 workspace_docs、skills、tool_plan、tool_policy、memory_namespaces、workflow_name、create_chat_entry、export_agent_factory 等关键字段。
  - blueprint 只负责设计，不得在此阶段创建仓库目录、写代码文件或修改 agents 导出。
  - 不得虚构不存在的工具、技能、模板或用户约束。
  - 优先复用现有工具；只有在明确无法满足需求时，才在 tool_plan.new_tools 中声明新本地工具。
  - 若声明新工具，只能提供 implementation_hint 或最小实现思路，不得伪装成已经落地的真实文件。
  - agent_id 必须归一化为 snake_case；若 requirements 未明确提供且无法稳定推断，应列入 missing_fields。
  - confirmation_required 必须为 true，且必须明确告知用户只有输入"确认创建"后才会进入实际生成阶段。
  - 必须输出 user_message 字段：向用户说明 blueprint 的核心设计思路、包含的功能模块、以及确认后会发生什么，语言要自然、口语化，不要重复 JSON 结构。
failure_modes:
  - case: incomplete_requirements
    effect: 无法生成稳定蓝图，后续脚手架生成风险高
  - case: conflicting_requirements
    effect: 蓝图不一致，进入生成阶段会导致错误实现
  - case: invalid_tool_plan
    effect: blueprint 中工具规划不可执行，无法安全交接给生成阶段
fallback_strategy:
  - when: incomplete_requirements
    action: 返回 missing_fields，并给出最少量、高价值的补充问题
  - when: conflicting_requirements
    action: 返回 conflicts，并要求用户明确取舍或优先级
  - when: invalid_tool_plan
    action: 收窄工具方案，优先回退为复用已有工具或简化能力边界
tool_policy:
  audit_logging: true
  sandbox_execution: false
  require_approval_for_write: false
subagent_allowed: false
dependencies: []
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: blueprint_design
  produces: pending_blueprint
  consumes:
    - requirements
    - existing_pending_blueprint
---
Use this skill to convert structured requirements into a reviewable AgentBlueprint.

Execution notes:
1. Normalize the requirements into a complete blueprint object instead of returning loose text.
2. Include workspace docs, skill plan, tool plan, tool policy, memory namespaces, workflow name, chat entry creation flag, and export flag.
3. Prefer existing tools first; only declare new local tools when reuse is insufficient.
4. For a new custom tool, include an implementation_hint or minimal runnable design intent in the tool blueprint, but do not create files in this step.
5. Save the coherent blueprint with `save_pending_blueprint` only after the blueprint is internally consistent.
6. Clearly tell the user that they must input `确认创建` before any repository files are actually written.
7. 【智能功能推断】如果 requirements 中的 `required_skills` 和 `required_tools` 为空，你需要从用户的原始需求描述中主动推断需要什么功能。不要因为 skills/tools 为空就生成一个没有功能的 agent。从 agent 的名称、角色和目标来推断它应该具备什么能力。