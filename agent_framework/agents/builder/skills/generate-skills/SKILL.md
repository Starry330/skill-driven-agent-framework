---
name: generate-skills
description: Generate protocol-driven skill packages for the target agent only after explicit confirmation and successful blueprint finalization. This skill is responsible only for rendering and writing skill package artifacts from the blueprint skill plan, and must not fabricate tools, protocol fields, or capabilities that are not declared in the blueprint.
triggers:
  - 生成skills
  - generate skills
  - 写入skills
required_tools:
  - generate_skills
permissions:
  - filesystem_write
input_schema:
  type: object
  required:
    - blueprint
  properties:
    blueprint:
      type: object
      description: 已 finalize 且允许进入生成阶段的 AgentBlueprint。
      properties:
        agent_id:
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
              triggers:
                type: array
                items:
                  type: string
              required_tools:
                type: array
                items:
                  type: string
              input_schema:
                type: object
              output_schema:
                type: object
              decision_logic:
                type: array
                items:
                  type: object
              constraints:
                type: array
                items:
                  type: string
              failure_modes:
                type: array
                items:
                  type: object
              fallback_strategy:
                type: array
                items:
                  type: object
              tool_policy:
                type: object
    session_state:
      type: object
      description: 当前 builder 会话状态，用于防止绕过确认直接写入。
      properties:
        awaiting_confirmation:
          type: boolean
        pending_blueprint_exists:
          type: boolean
        finalized_ready:
          type: boolean
    confirmation_input:
      type: string
      description: 用户确认文本，只有精确等于“确认创建”才允许写入。
    generation_context:
      type: object
      description: 可选生成上下文，例如目标目录、命名约束、模板来源。
      properties:
        target_agent_dir:
          type: string
        template_hint:
          type: string
        naming_style:
          type: string
output_schema:
  type: object
  required:
    - status
    - created_files
    - rendered_skills
    - next_action
  properties:
    status:
      type: string
      enum:
        - rejected_not_confirmed
        - need_skill_plan
        - generation_succeeded
        - generation_failed
    created_files:
      type: array
      description: 实际成功写入的 skill 文件路径，不得虚构。
      items:
        type: string
    rendered_skills:
      type: array
      description: 已成功渲染的 skill 名称列表。
      items:
        type: string
    issues:
      type: array
      description: 阻止生成或导致部分失败的问题列表。
      items:
        type: string
    generation_summary:
      type: string
      description: 对本次 skill 包生成结果的简洁总结。
    next_action:
      type: string
      enum:
        - wait_for_exact_confirmation
        - refine_blueprint_and_retry
        - continue_generation_pipeline
        - inspect_generated_skills
decision_logic:
  - if: blueprint.skills 为空、缺失，或 skill plan 不可解析
    return: need_skill_plan
  - if: session_state.awaiting_confirmation 不为 true，或 confirmation_input 不精确等于“确认创建”，或 session_state.finalized_ready 不为 true
    return: rejected_not_confirmed
  - if: blueprint.skills 可解析且已确认
    return: generation_succeeded_or_generation_failed_after_execution
constraints:
  - 该 skill 只负责根据 blueprint.skills 生成 skill 包，不得重写 blueprint、生成工具模块、生成 workspace 文档或生成 spec。
  - 只有当当前会话处于 awaiting_confirmation 状态、finalized_ready=true 且 confirmation_input 精确等于“确认创建”时，才允许写入文件。
  - 每个生成的 skill 都必须包含 required_tools 字段；若该 skill 无工具依赖，也必须显式写出 required_tools 字段，不得省略。
  - 每个协议驱动 skill 至少应包含 name、description、triggers、required_tools、input_schema、output_schema、decision_logic、constraints、failure_modes、fallback_strategy、tool_policy、enabled、metadata 等关键字段。
  - 不得生成 fake tool、fake protocol 字段、fake capability，所有 skill 内容都必须来源于 blueprint 中已声明的 skills 与工具规划。
  - 不得为 blueprint 未声明的 skill 自动补出额外工具依赖、额外权限或额外能力。
  - skill_name 必须可稳定映射为目录名，推荐 snake_case；若命名非法，应视为生成失败而不是自动脑补。
  - created_files 必须与真实写入结果一致；部分成功时必须如实返回已写入文件和失败原因。
failure_modes:
  - case: no_skill_plan
    effect: 无法定位需要生成的 skill 包，生成中止
  - case: not_confirmed
    effect: 禁止写入，保持等待确认状态
  - case: invalid_skill_schema
    effect: 目标 skill 缺少关键协议字段，生成结果不可加载
  - case: skill_render_failed
    effect: 某个或多个 skill 模板渲染失败，生成结果不完整
  - case: filesystem_write_failed
    effect: skill 内容已渲染但落盘失败，需返回部分结果
fallback_strategy:
  - when: no_skill_plan
    action: 提示先补全或修正 blueprint.skills，再重新执行生成
  - when: not_confirmed
    action: 明确提示只有输入“确认创建”才会开始写入 skill 文件
  - when: invalid_skill_schema
    action: 返回缺失字段或非法字段，要求回到 refine_agent_blueprint 修正 skill plan
  - when: skill_render_failed
    action: 返回具体 skill 名称和失败原因，指导用户修正蓝图后重试
  - when: filesystem_write_failed
    action: 返回已创建文件、失败文件和错误原因，允许后续重试或清理
tool_policy:
  audit_logging: true
  sandbox_execution: true
  require_approval_for_write: true
subagent_allowed: false
dependencies:
  - finalize_blueprint
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: skill_generation
  role: artifact_subgenerator
  consumes:
    - pending_blueprint
    - confirmation_input
  produces:
    - skill_packages
    - created_files
---
Use this skill during the act phase to render and write protocol-driven skill packages from blueprint.skills.

Execution notes:
1. Do not write any skill files before exact confirmation.
2. The only accepted confirmation input is `确认创建`.
3. Generate only the skill packages explicitly declared in the blueprint; do not invent extra skills, tools, or protocol fields.
4. Ensure every generated skill contains the required protocol structure and an explicit `required_tools` field.
5. On partial failure, return the exact skill name, created files, and concrete failure reason instead of reporting a fake full success.