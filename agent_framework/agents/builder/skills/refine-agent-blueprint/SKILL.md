---
name: refine-agent-blueprint
description: Incrementally refine an existing pending blueprint based on explicit user feedback without rebuilding it from scratch. This skill applies targeted updates to the current blueprint, preserves unaffected structure, records changed fields, and stores the refined pending blueprint for revalidation and reconfirmation. It must not generate repository files or silently replace large sections of the blueprint.
triggers:
  - 修改蓝图
  - refine blueprint
  - 调整agent
  - 修改agent设计
  - 更新蓝图
required_tools:
  - refine_agent_blueprint
  - save_pending_blueprint
permissions: []
input_schema:
  type: object
  required:
    - refinement
  properties:
    base_blueprint:
      type: object
      description: 当前待修改的 pending AgentBlueprint；若为空，则表示需要从当前会话的 pending blueprint 读取。
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
    refinement:
      type: object
      description: 用户本轮明确提出的增量修改内容，必须被视为局部补丁而不是全量重建指令。
      properties:
        field_updates:
          type: object
          description: 需要更新的字段及其新值。
        field_removals:
          type: array
          description: 用户明确要求删除的字段或子项路径。
          items:
            type: string
        field_replacements:
          type: array
          description: 用户明确要求整体替换的字段列表。
          items:
            type: string
        user_feedback_text:
          type: string
          description: 原始用户反馈，可用于解释修改意图，但不得覆盖结构化 refinement。
    refinement_context:
      type: object
      description: 可选上下文，用于控制增量修改策略。
      properties:
        allow_structural_replace:
          type: boolean
        require_minimal_patch:
          type: boolean
        preserve_tool_plan_by_default:
          type: boolean
        preserve_workspace_by_default:
          type: boolean
output_schema:
  type: object
  required:
    - status
    - blueprint
    - changed_fields
    - next_action
  properties:
    status:
      type: string
      enum:
        - need_existing_blueprint
        - need_more_info
        - conflict_detected
        - refinement_applied
    blueprint:
      type: object
      description: 应用增量修改后的新 pending blueprint。
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
    changed_fields:
      type: array
      description: 本轮实际被修改的字段路径列表。
      items:
        type: string
    preserved_fields:
      type: array
      description: 因未被显式提及而保持不变的关键字段列表。
      items:
        type: string
    conflicts:
      type: array
      description: 用户反馈与现有蓝图之间的冲突项。
      items:
        type: string
    issues:
      type: array
      description: 当前 refinement 中阻止稳定落地的问题列表。
      items:
        type: string
    refinement_summary:
      type: string
      description: 对本轮增量修改结果的简洁总结。
    reconfirmation_required:
      type: boolean
      description: refinement_applied 后必须重新确认，默认应为 true。
    next_action:
      type: string
      enum:
        - design_initial_blueprint
        - ask_user_for_clarification
        - ask_user_to_resolve_conflicts
        - rerun_tool_planning
        - rerun_finalize_blueprint
decision_logic:
  - if: 当前不存在 pending blueprint，且未提供可用的 base_blueprint
    return: need_existing_blueprint
  - if: refinement 缺少可执行的字段更新信息，或用户反馈无法映射为稳定补丁
    return: need_more_info
  - if: 用户反馈与现有字段冲突，且用户未明确要求覆盖、删除或替换
    return: conflict_detected
  - if: base_blueprint 存在且 refinement 可作为局部补丁稳定应用
    return: refinement_applied
constraints:
  - 不允许全量重建 blueprint；该 skill 只能做局部增量修改。
  - 必须保留已有结构，除非用户明确要求替换、删除或覆盖冲突字段。
  - 只能修改用户显式提到的字段，不能顺手改动未提及的核心设计。
  - 默认保留 workspace_docs、skills、tool_plan、tool_policy、memory_namespaces 等关键结构；若用户未明确要求变动，不得隐式重算。
  - 若 refinement 影响 skills、tool_plan、tool_policy 或 workflow 边界，必须在结果中显式提示后续需要重新执行对应阶段，而不是偷偷联动改写全部下游内容。
  - refinement_applied 后必须将 confirmation_required 置为 true，并要求重新 finalize 和重新确认。
  - 该 skill 只负责修改和保存 pending blueprint，不得创建仓库文件、生成脚手架或伪造“已生成”状态。
  - changed_fields 必须只包含真实变更，不得把未修改字段误报为已修改。
failure_modes:
  - case: no_pending_blueprint
    effect: 无法执行增量修改，必须先设计初始 blueprint
  - case: ambiguous_refinement
    effect: 用户反馈无法稳定映射到具体字段，修改结果不可靠
  - case: conflicting_refinement
    effect: 修改请求与现有蓝图冲突，若不澄清会导致 blueprint 不稳定
  - case: invalid_patch_scope
    effect: refinement 实际上等价于全量重建，违背增量修改约束
  - case: downstream_dependency_impact
    effect: 修改已影响 tool_plan、skills 或 finalize 条件，必须重新校验
fallback_strategy:
  - when: no_pending_blueprint
    action: 提醒先执行 design_agent_blueprint 形成初始 pending blueprint
  - when: ambiguous_refinement
    action: 返回需要澄清的字段，并要求用户用更明确的局部修改指令补充
  - when: conflicting_refinement
    action: 返回冲突项，并要求用户确认是覆盖旧值、删除旧值还是保留原设计
  - when: invalid_patch_scope
    action: 拒绝将本次请求当作 refinement 处理，并建议回到 design_agent_blueprint 重新设计
  - when: downstream_dependency_impact
    action: 提示需要重新执行 plan_agent_tools 或 finalize_blueprint，以确保蓝图重新闭合
tool_policy:
  audit_logging: true
  sandbox_execution: false
  require_approval_for_write: false
subagent_allowed: false
dependencies:
  - design_agent_blueprint
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: blueprint_refinement
  produces:
    - refined_pending_blueprint
    - changed_fields
  consumes:
    - pending_blueprint
    - refinement
---
Use this skill to update the current pending blueprint through a minimal patch instead of rebuilding it.

Execution notes:
1. Only change fields explicitly mentioned by the user or explicitly listed in refinement.field_updates, field_removals, or field_replacements.
2. Preserve existing workspace docs, skills, tool plan, tool policy, and memory namespaces unless the refinement directly changes them.
3. Treat ambiguous user feedback as `need_more_info` instead of guessing a patch.
4. If the refinement changes tool scope, skill dependencies, workflow structure, or policy boundaries, explicitly require downstream revalidation.
5. Save the refined pending blueprint after the patch is internally coherent.
6. Always require reconfirmation after refinement; the user must re-finalize and re-confirm before any generation step.