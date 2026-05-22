---
name: generate-spec
description: Generate the final spec.py and target-agent __init__.py only after explicit confirmation and successful blueprint finalization. This skill is responsible only for rendering the target agent's spec module and package export file, and must not update global registry exports or fabricate dependencies that are not declared in the blueprint.
triggers:
  - 生成spec
  - generate spec
  - 写入spec
required_tools:
  - generate_spec
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
    artifact_context:
      type: object
      description: 前置生成产物上下文，用于确保 spec 渲染所依赖的信息已闭合。
      properties:
        workspace_generated:
          type: boolean
        skills_generated:
          type: boolean
        tools_generated:
          type: boolean
        target_agent_dir:
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
        - need_generation_prerequisites
        - generation_succeeded
        - generation_failed
    created_files:
      type: array
      description: 实际成功写入的 spec.py 和 __init__.py 文件路径，不得虚构。
      items:
        type: string
    exported_symbols:
      type: array
      description: 在目标 agent 包 __init__.py 中实际导出的符号名称。
      items:
        type: string
    issues:
      type: array
      description: 阻止 spec 生成或导致生成失败的问题列表。
      items:
        type: string
    generation_summary:
      type: string
      description: 对本次 spec 模块生成结果的简洁总结。
    next_action:
      type: string
      enum:
        - wait_for_exact_confirmation
        - complete_generation_prerequisites
        - continue_generation_pipeline
        - inspect_generated_spec
decision_logic:
  - if: session_state.awaiting_confirmation 不为 true，或 confirmation_input 不精确等于“确认创建”，或 session_state.finalized_ready 不为 true
    return: rejected_not_confirmed
  - if: blueprint 缺少 agent_id、workflow_name、tool_policy、skills，或 artifact_context 中前置产物未满足 spec 渲染需要
    return: need_generation_prerequisites
  - if: 已确认、blueprint 可解析、前置依赖闭合
    return: generation_succeeded_or_generation_failed_after_execution
constraints:
  - 该 skill 只生成目标 agent 目录下的 spec.py 和 __init__.py，不得写入其他文件。
  - 不得更新 agent_framework/agents/__init__.py 或其他全局注册文件；全局导出应由专门的导出更新步骤负责。
  - 只有当当前会话处于 awaiting_confirmation 状态、finalized_ready=true 且 confirmation_input 精确等于“确认创建”时，才允许写入文件。
  - 生成结果必须与 blueprint.tool_policy、workspace 配置、skill 规划、tool 规划和 workflow_name 保持一致，不得私自补充未声明的能力。
  - spec.py 中的 agent spec 定义必须能够稳定引用 blueprint 中声明的 skills、tools、workspace 和 workflow 配置，不得生成悬空引用。
  - __init__.py 只应导出目标 agent 包内需要暴露的工厂函数、spec 对象或约定导出符号，不得伪造不存在的导出。
  - created_files 和 exported_symbols 必须与真实写入结果一致；部分成功时必须如实返回。
failure_modes:
  - case: not_confirmed
    effect: 禁止写入，保持等待确认状态
  - case: missing_generation_prerequisites
    effect: spec 渲染依赖未闭合，无法稳定生成
  - case: spec_render_failed
    effect: spec.py 或 __init__.py 模板渲染失败，agent 无法注册
  - case: invalid_symbol_export
    effect: __init__.py 导出符号与实际实现不一致，包导入失败
  - case: filesystem_write_failed
    effect: 内容已渲染但落盘失败，需返回部分结果
fallback_strategy:
  - when: not_confirmed
    action: 明确提示只有输入“确认创建”才会开始写入 spec 文件
  - when: missing_generation_prerequisites
    action: 返回缺失的前置条件，提示先完成 workspace、skills、tools 生成或修正 blueprint
  - when: spec_render_failed
    action: 返回具体渲染失败原因和对应文件，指导用户修正 blueprint 或模板后重试
  - when: invalid_symbol_export
    action: 返回无效导出符号列表，要求修正 spec 导出定义
  - when: filesystem_write_failed
    action: 返回已创建文件、失败文件和错误原因，允许后续重试或清理
tool_policy:
  audit_logging: true
  sandbox_execution: true
  require_approval_for_write: true
subagent_allowed: false
dependencies:
  - generate_workspace
  - generate_skills
  - generate_tools
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: spec_generation
  role: artifact_subgenerator
  consumes:
    - pending_blueprint
    - confirmation_input
    - generated_workspace_artifacts
    - generated_skill_artifacts
    - generated_tool_artifacts
  produces:
    - spec_module
    - package_init
---
Use this skill during the act phase to generate the final target-agent spec module and package export file.

Execution notes:
1. Do not write spec.py or __init__.py before exact confirmation.
2. The only accepted confirmation input is `确认创建`.
3. Generate only spec.py and the target agent package __init__.py; do not modify any global exports in this step.
4. Ensure spec.py is consistent with the finalized blueprint, workspace layout, skill plan, tool plan, tool policy, and workflow configuration.
5. Ensure __init__.py exports only real symbols that are actually generated and resolvable.
6. On partial failure, return the exact created files, invalid exports, and concrete failure reason instead of reporting fake success.