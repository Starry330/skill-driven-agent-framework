---
name: finalize-blueprint
description: Validate whether the pending AgentBlueprint is complete, internally consistent, dependency-closed, and safe to enter the user confirmation and generation stage. This skill only performs blueprint validation and gating; it must not generate repository files or execute scaffold creation.
triggers:
  - finalize blueprint
  - 完成蓝图
  - 准备生成
  - 校验蓝图
  - 确认前检查
required_tools:
  - finalize_blueprint
permissions: []
input_schema:
  type: object
  required:
    - blueprint
  properties:
    blueprint:
      type: object
      description: 当前待确认的 pending AgentBlueprint。
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
        skills:
          type: array
          items:
            type: object
        tool_plan:
          type: object
        tool_policy:
          type: object
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
    validation_context:
      type: object
      description: 可选的校验上下文，例如模板基线、现有 agent 名称集合、生成约束等。
      properties:
        template_hint:
          type: string
        existing_agent_ids:
          type: array
          items:
            type: string
        allow_local_tools:
          type: boolean
        allow_remote_mcp:
          type: boolean
output_schema:
  type: object
  required:
    - status
    - issues
    - validation_report
    - next_action
  properties:
    status:
      type: string
      enum:
        - ready_to_generate
        - need_more_info
        - conflict_detected
    issues:
      type: array
      description: 当前阻止 blueprint 进入确认/生成阶段的所有问题。
      items:
        type: string
    validation_report:
      type: object
      description: 结构化校验结果，供 refine 和 confirmation 阶段直接消费。
      properties:
        completeness_ok:
          type: boolean
        consistency_ok:
          type: boolean
        dependency_closure_ok:
          type: boolean
        tool_plan_ok:
          type: boolean
        policy_ok:
          type: boolean
        naming_ok:
          type: boolean
        confirmation_gate_ok:
          type: boolean
        checked_fields:
          type: array
          items:
            type: string
        missing_fields:
          type: array
          items:
            type: string
        conflicts:
          type: array
          items:
            type: string
        unresolved_dependencies:
          type: array
          items:
            type: string
        risky_items:
          type: array
          items:
            type: string
    next_action:
      type: string
      enum:
        - ask_user_for_missing_info
        - ask_user_to_resolve_conflicts
        - ask_user_to_confirm_creation
    confirmation_message:
      type: string
      description: 当 status=ready_to_generate 时，提示用户输入“确认创建”进入实际生成。
decision_logic:
  - if: blueprint 缺少 agent_id、role、goal、skills、tool_plan、tool_policy、workspace_docs 或其他关键字段
    return: need_more_info
  - if: blueprint 内部存在冲突、未闭合依赖、非法命名、工具策略不一致或风险项未处理
    return: conflict_detected
  - if: blueprint 完整、内部一致、依赖闭合，且满足确认门槛
    return: ready_to_generate
constraints:
  - 必须明确返回 ready_to_generate、need_more_info、conflict_detected 三种状态之一，不得返回模糊描述替代状态值。
  - 不得跳过字段完整性检查、依赖闭合检查、工具规划检查和策略一致性检查。
  - 该阶段只负责校验和准入判断，不得创建仓库目录、写代码文件、更新 agents 导出或执行 scaffold 生成。
  - 不得虚构“已通过”的检查结果；所有 validation_report 字段必须与实际蓝图内容一致。
  - 对 need_more_info 和 conflict_detected 必须给出可执行的问题列表，而不是笼统说“蓝图不完整”。
  - 若 validation_context.existing_agent_ids 中已存在相同 agent_id，必须判定为冲突。
  - confirmation_required 必须为 true；若缺失或为 false，不能直接进入 ready_to_generate。
  - 必须输出 user_message 字段：向用户说明当前蓝图校验结果、通过了哪些检查、哪些还需要补充，语言要自然、口语化，不要重复 JSON 结构。
failure_modes:
  - case: blueprint_incomplete
    effect: 蓝图缺少最小可生成字段，无法进入确认阶段
  - case: blueprint_conflicting
    effect: 蓝图内部语义冲突或策略冲突，进入生成会导致错误实现
  - case: dependency_not_closed
    effect: skill、tool、workspace 或 memory 之间存在未闭合依赖，无法稳定生成
  - case: unsafe_generation_gate
    effect: 缺失确认门槛或命名冲突，不能进入实际生成
fallback_strategy:
  - when: blueprint_incomplete
    action: 返回 missing_fields，并指示回到 refine_agent_blueprint 或 collect_agent_requirements 补全信息
  - when: blueprint_conflicting
    action: 返回 conflicts，并要求用户明确优先级或修改 blueprint
  - when: dependency_not_closed
    action: 返回 unresolved_dependencies，并要求补齐 skill、tool、workspace 或 memory 的对应关系
  - when: unsafe_generation_gate
    action: 拒绝进入生成阶段，并要求修复确认门槛、命名冲突或策略风险
tool_policy:
  audit_logging: true
  sandbox_execution: false
  require_approval_for_write: false
subagent_allowed: false
dependencies:
  - design_agent_blueprint
  - refine_agent_blueprint
  - plan_agent_tools
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: blueprint_finalization
  consumes:
    - pending_blueprint
  produces:
    - validation_report
    - generation_gate_decision
---
Use this skill to validate whether the pending blueprint can safely enter confirmation and generation.

Execution notes:
1. Validate the blueprint across completeness, consistency, dependency closure, tool plan validity, policy consistency, naming rules, and confirmation gate readiness.
2. Always return one of: `ready_to_generate`, `need_more_info`, or `conflict_detected`.
3. When the blueprint is not ready, provide explicit issues grouped as missing fields, conflicts, unresolved dependencies, or risky items.
4. When the blueprint is ready, set `next_action` to `ask_user_to_confirm_creation` and clearly tell the user they must input `确认创建` before any repository files are written.
5. Do not generate files, code, or scaffold artifacts in this step.