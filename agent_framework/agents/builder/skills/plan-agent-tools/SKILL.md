---
name: plan-agent-tools
description: Analyze the blueprint and decide whether each required capability should reuse existing framework tools or introduce new local Python tool implementations. This skill produces a structured ToolPlan, aligns skill-to-tool references, and updates the pending blueprint, but must not generate repository files or pretend that undeclared tools already exist.
triggers:
  - 工具
  - tool
  - 工具规划
  - 创建agent
  - 生成agent
  - 规划工具
required_tools:
  - plan_agent_tools
  - save_pending_blueprint
permissions: []
input_schema:
  type: object
  required:
    - blueprint
  properties:
    blueprint:
      type: object
      description: 当前待设计的 AgentBlueprint，至少应包含 skills、goal、constraints 和 tool_policy。
      properties:
        agent_id:
          type: string
        name:
          type: string
        role:
          type: string
        goal:
          type: string
        skills:
          type: array
          items:
            type: object
            properties:
              skill_name:
                type: string
              purpose:
                type: string
              required_tools:
                type: array
                items:
                  type: string
        user_constraints:
          type: array
          items:
            type: string
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
    available_tools:
      type: array
      description: 当前框架中可复用的已存在工具列表，用于做 reuse 判断。
      items:
        type: object
        properties:
          tool_name:
            type: string
          purpose:
            type: string
          capabilities:
            type: array
            items:
              type: string
          supports_io:
            type: boolean
          supports_side_effects:
            type: boolean
          requires_approval:
            type: boolean
    existing_tool_plan:
      type: object
      description: 已存在的工具规划，可用于增量修订而不是完全重建。
    planning_context:
      type: object
      description: 可选规划上下文，例如模板偏好、生成阶段约束、实现边界。
      properties:
        template_hint:
          type: string
        prefer_reuse:
          type: boolean
        local_tools_only:
          type: boolean
output_schema:
  type: object
  required:
    - status
    - tool_plan
    - issues
    - next_action
  properties:
    status:
      type: string
      enum:
        - tool_plan_ready
        - need_more_info
        - tool_gap_unresolved
        - policy_conflict_detected
    tool_plan:
      type: object
      description: 结构化 ToolPlan，供 blueprint finalize 和 act phase 直接消费。
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
              matched_skills:
                type: array
                items:
                  type: string
              coverage_reason:
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
              matched_skills:
                type: array
                items:
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
        unresolved_gaps:
          type: array
          items:
            type: string
    issues:
      type: array
      description: 当前工具规划中的问题、冲突或未解决缺口。
      items:
        type: string
    alignment_report:
      type: object
      description: skill.required_tools 与 tool_plan 的对齐结果。
      properties:
        all_skill_references_resolved:
          type: boolean
        unresolved_skill_tool_refs:
          type: array
          items:
            type: string
        adjusted_skill_entries:
          type: array
          items:
            type: string
    next_action:
      type: string
      enum:
        - continue_blueprint_design
        - ask_user_for_tool_scope
        - refine_blueprint_constraints
        - finalize_blueprint
decision_logic:
  - if: blueprint 缺少 skills、goal、tool_policy 或关键能力边界，无法稳定规划工具
    return: need_more_info
  - if: 所需能力可由现有工具覆盖至少 80%，且满足约束与权限要求
    return: tool_plan_ready
  - if: 需要新的 IO、文件写入、执行、副作用能力，且 tool_policy 允许本地工具实现
    return: tool_plan_ready
  - if: 存在工具缺口，但需求边界过宽或能力定义不清，无法收敛为可实现的新工具
    return: tool_gap_unresolved
  - if: 需求要求新工具，但 tool_policy 禁止本地工具，或只允许本地工具但需求实际依赖远程 MCP
    return: policy_conflict_detected
constraints:
  - 该 skill 只负责编制 ToolPlan 和更新 pending blueprint，不得生成工具代码文件、远程 MCP server 或任何仓库产物。
  - 输出必须是完整的结构化 ToolPlan，不得只返回松散自然语言描述。
  - 不得输出模糊工具名、fake tool、占位工具或未声明实现边界的伪方案。
  - 优先复用现有框架工具；只有在复用无法满足关键能力时，才声明 new_tools。
  - new_tools 必须是第一版可落地的本地 Python 工具，不得规划远程 MCP server。
  - 每个 new_tool 都必须包含 purpose、reason、io_schema、implementation_hint 和 risk_level，不得只给名称。
  - 每个 skill.required_tools 都必须能在 reuse_tools 或 new_tools 中找到对应来源，不能留下悬空引用。
  - tool_name 应保持稳定、明确、可映射为后续本地模块命名，推荐 snake_case。
  - 若某项需求可通过收窄能力边界来避免新增工具，应优先收窄需求而不是扩张工具面。
failure_modes:
  - case: blueprint_missing_tool_context
    effect: 无法判断需要哪些工具，工具规划不稳定
  - case: tool_gap_unresolved
    effect: 关键能力缺口未解决，不能进入可生成状态
  - case: invalid_new_tool_definition
    effect: 新工具定义不完整，后续生成阶段无法落地
  - case: policy_conflict
    effect: 工具需求与 tool_policy 冲突，无法形成合法工具方案
  - case: unresolved_skill_tool_alignment
    effect: skills.required_tools 与 tool_plan 不一致，后续 spec 和 skill 生成会失败
fallback_strategy:
  - when: blueprint_missing_tool_context
    action: 返回缺失上下文，并要求补充 skills、goal、tool_policy 或能力边界
  - when: tool_gap_unresolved
    action: 明确说明能力缺口，并要求用户收窄需求、删减副作用能力或接受新增工具方案
  - when: invalid_new_tool_definition
    action: 返回具体缺失字段，要求 refine tool plan 后重试
  - when: policy_conflict
    action: 返回冲突项，要求修改 tool_policy 或调整能力边界
  - when: unresolved_skill_tool_alignment
    action: 返回未对齐的 skill.required_tools 项，要求同步修正 blueprint.skills
tool_policy:
  audit_logging: true
  sandbox_execution: false
  require_approval_for_write: false
  tool_decision_rules:
    - 是否已有工具满足至少80%需求
    - 是否涉及 IO（API / DB / 文件）
    - 是否需要副作用（写入 / 执行）
    - 是否涉及权限控制
    - 是否可通过收窄需求避免新增工具
    - 是否能以第一版本地 Python 工具稳定落地
subagent_allowed: false
dependencies: []
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: tool_planning
  produces: tool_plan
  consumes:
    - blueprint
    - available_tools
    - existing_tool_plan
---
Use this skill when tool strategy is part of the agent design.

Execution notes:
1. Prefer existing framework tools whenever they satisfy the required capability with sufficient coverage and acceptable policy alignment.
2. If existing tools are insufficient, design a new local Python tool in the ToolPlan using a simple runnable implementation direction, but do not generate files in this step.
3. Ensure every skill.required_tools entry maps to a tool that will actually exist through reuse or future local generation.
4. Update and save the pending blueprint after the tool plan has been made internally coherent.
5. When tool gaps remain unresolved, explain the gap concretely and ask the user to narrow the requirement instead of inventing fake tools.