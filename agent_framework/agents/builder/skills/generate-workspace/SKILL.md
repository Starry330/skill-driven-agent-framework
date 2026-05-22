---
name: generate-workspace
description: Generate workspace bootstrap documents for the target agent only after explicit confirmation and successful blueprint finalization. This skill is responsible only for rendering and writing the workspace-level bootstrap artifacts declared in the finalized blueprint, and must not generate skill files, tool modules, spec files, or global export files.
triggers:
  - 生成workspace
  - generate workspace
  - 写入workspace
  - 生成工作区
required_tools:
  - generate_workspace
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
            properties:
              name:
                type: string
              purpose:
                type: string
              required:
                type: boolean
        style_constraints:
          type: array
          items:
            type: string
        tool_policy:
          type: object
        memory_namespaces:
          type: array
          items:
            type: string
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
    generation_context:
      type: object
      description: 可选生成上下文，例如目标目录、workspace 根路径、模板来源。
      properties:
        target_agent_dir:
          type: string
        target_workspace_dir:
          type: string
        template_hint:
          type: string
        comment_style:
          type: string
output_schema:
  type: object
  required:
    - status
    - created_files
    - rendered_docs
    - next_action
  properties:
    status:
      type: string
      enum:
        - rejected_not_confirmed
        - need_workspace_plan
        - generation_succeeded
        - generation_failed
    created_files:
      type: array
      description: 实际成功写入的 workspace/bootstrap 文档路径，不得虚构。
      items:
        type: string
    rendered_docs:
      type: array
      description: 实际成功渲染并写入的 workspace 文档名称列表。
      items:
        type: string
    issues:
      type: array
      description: 阻止 workspace 生成或导致部分失败的问题列表。
      items:
        type: string
    generation_summary:
      type: string
      description: 对本次 workspace 文档生成结果的简洁总结。
    next_action:
      type: string
      enum:
        - wait_for_exact_confirmation
        - refine_blueprint_and_retry
        - continue_generation_pipeline
        - inspect_generated_workspace
decision_logic:
  - if: session_state.awaiting_confirmation 不为 true，或 confirmation_input 不精确等于“确认创建”，或 session_state.finalized_ready 不为 true
    return: rejected_not_confirmed
  - if: blueprint.workspace_docs 为空、缺失，或 workspace 规划不可解析
    return: need_workspace_plan
  - if: blueprint.workspace_docs 可解析且已确认
    return: generation_succeeded_or_generation_failed_after_execution
constraints:
  - 该 skill 只负责根据 blueprint.workspace_docs 生成 workspace/bootstrap 文档，不得生成 skill 文件、tool 模块、spec.py、__init__.py 或全局导出文件。
  - 只有当当前会话处于 awaiting_confirmation 状态、finalized_ready=true 且 confirmation_input 精确等于“确认创建”时，才允许写入文件。
  - workspace 文档必须严格来源于 blueprint.workspace_docs，不得补出蓝图未声明的额外 bootstrap 文件。
  - 每个生成的 workspace 文档都必须与其 name、purpose 和 required 属性保持一致，不得生成与蓝图用途不符的内容。
  - 若某个 required=true 的 workspace 文档无法生成，应视为生成失败，而不是静默跳过。
  - workspace 文档应服务于 agent bootstrap，包括但不限于 AGENTS.md、SOUL.md、TOOLS.md、USER.md、memory/MEMORY.md 等蓝图声明内容；但不得假定所有这些文件都必须存在，必须以 blueprint.workspace_docs 为准。
  - 文档内容应保持清晰、克制、面向后续 agent 运行与维护，采用简洁中文说明，不得堆砌空洞描述。
  - created_files 和 rendered_docs 必须与真实写入结果一致；部分成功时必须如实返回。
failure_modes:
  - case: not_confirmed
    effect: 禁止写入，保持等待确认状态
  - case: no_workspace_plan
    effect: 无法定位需要生成的 workspace 文档，生成中止
  - case: invalid_workspace_doc_blueprint
    effect: 某个 workspace 文档蓝图缺少必要字段，无法稳定生成
  - case: workspace_render_failed
    effect: 某个或多个 bootstrap 文档渲染失败，workspace 不完整
  - case: filesystem_write_failed
    effect: 文档内容已渲染但落盘失败，需返回部分结果
  - case: required_doc_missing
    effect: 必需的 workspace 文档未成功生成，不能视为成功
fallback_strategy:
  - when: not_confirmed
    action: 明确提示只有输入“确认创建”才会开始写入 workspace 文档
  - when: no_workspace_plan
    action: 提示先补全或修正 blueprint.workspace_docs，再重新执行生成
  - when: invalid_workspace_doc_blueprint
    action: 返回具体缺失字段或非法字段，要求回到 refine_agent_blueprint 修正 workspace 规划
  - when: workspace_render_failed
    action: 返回具体文档名称和失败原因，指导用户修正蓝图或模板后重试
  - when: filesystem_write_failed
    action: 返回已创建文件、失败路径和错误原因，允许后续重试或清理
  - when: required_doc_missing
    action: 拒绝将本阶段标记为成功，并要求修复必需文档后再继续
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
  stage: workspace_generation
  role: artifact_subgenerator
  consumes:
    - pending_blueprint
    - confirmation_input
  produces:
    - workspace_bootstrap_artifacts
    - created_files
---
Use this skill during the act phase to render and write workspace bootstrap documents from blueprint.workspace_docs.

Execution notes:
1. Do not write any workspace files before exact confirmation.
2. The only accepted confirmation input is `确认创建`.
3. Generate only the workspace/bootstrap documents explicitly declared in blueprint.workspace_docs; do not invent extra files.
4. Do not generate skill files, tool modules, spec files, or global exports in this step.
5. Treat required workspace documents as hard requirements; if any required document fails, do not report a fake full success.
6. On partial failure, return the exact created files, failed document names, and concrete failure reasons.