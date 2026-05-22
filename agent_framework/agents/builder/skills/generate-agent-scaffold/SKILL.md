---
name: generate-agent-scaffold
description: Compatibility orchestration skill that generates a full runnable agent scaffold only after explicit user confirmation. This skill acts as a gated wrapper over workspace generation, skill generation, tool generation, spec generation, and post-generation validation. It must not bypass confirmation or fabricate created artifacts.
triggers:
  - 确认创建
  - 生成脚手架
  - scaffold
  - create now
  - 开始创建
required_tools:
  - generate_agent_scaffold
  - validate_generated_agent
permissions:
  - filesystem_write
input_schema:
  type: object
  required:
    - blueprint
  properties:
    blueprint:
      type: object
      description: 已完成设计并通过 finalize 的 AgentBlueprint。
      properties:
        agent_id:
          type: string
        name:
          type: string
        role:
          type: string
        goal:
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
    session_state:
      type: object
      description: 当前 builder 会话状态，用于判断是否处于等待确认阶段。
      properties:
        awaiting_confirmation:
          type: boolean
        pending_blueprint_exists:
          type: boolean
        finalized_ready:
          type: boolean
    confirmation_input:
      type: string
      description: 用户当前输入的确认文本，只有精确等于“确认创建”才允许写入。
    finalization_report:
      type: object
      description: 来自 finalize_blueprint 的准入结果，可用于避免未通过 finalize 就直接生成。
      properties:
        status:
          type: string
          enum:
            - ready_to_generate
            - need_more_info
            - conflict_detected
        issues:
          type: array
          items:
            type: string
output_schema:
  type: object
  required:
    - status
    - created_files
    - next_action
  properties:
    status:
      type: string
      enum:
        - rejected_not_confirmed
        - need_blueprint
        - need_finalization
        - generation_succeeded
        - generation_failed
    created_files:
      type: array
      description: 实际创建成功的文件路径列表，不得虚构。
      items:
        type: string
    validation_status:
      type: string
      description: 生成后校验结果。
      enum:
        - not_run
        - passed
        - failed
    issues:
      type: array
      description: 阻止生成或生成后校验失败的问题列表。
      items:
        type: string
    generation_summary:
      type: string
      description: 对本次生成结果的简洁总结。
    next_action:
      type: string
      enum:
        - wait_for_exact_confirmation
        - complete_blueprint_design
        - run_finalize_blueprint
        - inspect_generated_agent
        - refine_blueprint_and_retry
decision_logic:
  - if: 不存在 pending blueprint 或 blueprint 为空
    return: need_blueprint
  - if: session_state.awaiting_confirmation 不为 true，或 confirmation_input 不精确等于“确认创建”
    return: rejected_not_confirmed
  - if: finalization_report.status 不等于 ready_to_generate，或 session_state.finalized_ready 不为 true
    return: need_finalization
  - if: 已确认且 blueprint 已通过 finalize 校验
    return: generation_succeeded_or_generation_failed_after_execution
constraints:
  - 该 skill 只负责编排生成与生成后校验，不负责重新设计 blueprint，也不负责定义各生成阶段的内部细节。
  - 只有当 confirmation_input 精确等于“确认创建”且当前会话处于 awaiting_confirmation 状态时，才允许触发任何写入。
  - 不得在未确认时调用任何文件写入型生成流程。
  - 生成前必须满足 blueprint 已 finalize 且状态为 ready_to_generate，不得跳过准入检查。
  - created_files 必须来源于真实生成结果，不得伪造或预测未来文件。
  - 生成完成后必须调用 validate_generated_agent，除非生成阶段本身已失败。
  - 若生成部分成功但整体失败，必须如实返回已创建文件与失败问题，不得伪装为全成功。
failure_modes:
  - case: no_pending_blueprint
    effect: 无法执行生成，必须先完成 blueprint 设计
  - case: not_confirmed
    effect: 禁止写入，保持在等待确认状态
  - case: blueprint_not_finalized
    effect: 不能进入生成阶段，必须先 finalize 或 refine
  - case: partial_generation_failure
    effect: 可能产生部分文件，需返回 created_files 与失败原因
  - case: post_generation_validation_failed
    effect: 脚手架已生成但质量未达标，需要修复或重试
fallback_strategy:
  - when: no_pending_blueprint
    action: 提醒先完成 blueprint 设计并保存 pending blueprint
  - when: not_confirmed
    action: 明确提示只有输入“确认创建”才会开始写入文件
  - when: blueprint_not_finalized
    action: 提示先运行 finalize_blueprint，必要时回到 refine_agent_blueprint
  - when: partial_generation_failure
    action: 返回已创建文件和失败步骤，指导用户修复 blueprint 或重试生成
  - when: post_generation_validation_failed
    action: 返回校验问题，建议执行 refine_agent_blueprint 后重新生成
tool_policy:
  audit_logging: true
  sandbox_execution: true
  require_approval_for_write: true
subagent_allowed: false
dependencies:
  - generate_workspace
  - generate_skills
  - generate_tools
  - generate_spec
  - validate_generated_agent
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: scaffold_generation
  role: compatibility_orchestrator
  consumes:
    - pending_blueprint
    - finalization_report
    - confirmation_input
  produces:
    - created_files
    - validation_status
---
Use this skill only when the current builder session is explicitly waiting for confirmation and the user has entered `确认创建`.

Execution notes:
1. Do not call any file-writing generation flow before exact confirmation.
2. The only accepted confirmation input is `确认创建`; near matches or paraphrases must be rejected.
3. Treat this skill as an orchestration wrapper over workspace generation, skill generation, tool generation, spec generation, and post-generation validation.
4. Always run `validate_generated_agent` after generation unless generation itself fails before artifacts are created.
5. Return actual created files and validation results; do not fabricate successful outputs.