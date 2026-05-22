---
name: generate-tools
description: Generate real local Python tool implementations declared in the finalized blueprint only after explicit confirmation. This skill materializes only blueprint.tool_plan.new_tools into runnable local tool modules, and must not fabricate placeholder tools, remote MCP servers, or undeclared capabilities.
triggers:
  - 生成tools
  - generate tools
  - 写入tools
  - 生成工具
required_tools:
  - generate_tools
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
      description: 可选生成上下文，例如目标目录、模板来源、代码风格约束。
      properties:
        target_agent_dir:
          type: string
        target_tools_dir:
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
    - generated_tools
    - next_action
  properties:
    status:
      type: string
      enum:
        - rejected_not_confirmed
        - no_new_tools_required
        - generation_succeeded
        - generation_failed
    created_files:
      type: array
      description: 实际成功写入的本地工具文件路径，不得虚构。
      items:
        type: string
    generated_tools:
      type: array
      description: 实际成功生成的本地工具名称列表。
      items:
        type: string
    reused_tools:
      type: array
      description: blueprint 中声明为复用、因此不会落盘生成的工具名称列表。
      items:
        type: string
    issues:
      type: array
      description: 阻止工具生成或导致部分失败的问题列表。
      items:
        type: string
    generation_summary:
      type: string
      description: 对本次工具生成结果的简洁总结。
    next_action:
      type: string
      enum:
        - wait_for_exact_confirmation
        - continue_generation_pipeline
        - inspect_generated_tools
        - refine_tool_plan_and_retry
decision_logic:
  - if: session_state.awaiting_confirmation 不为 true，或 confirmation_input 不精确等于“确认创建”，或 session_state.finalized_ready 不为 true
    return: rejected_not_confirmed
  - if: blueprint.tool_plan.new_tools 为空，且 tool_plan 仅复用现有工具
    return: no_new_tools_required
  - if: blueprint.tool_plan.new_tools 非空，且 tool_policy.allow_local_tools=true
    return: generation_succeeded_or_generation_failed_after_execution
constraints:
  - 该 skill 只负责生成 blueprint.tool_plan.new_tools 中声明的真实本地 Python 工具实现，不得修改 blueprint，不得生成 workspace、skills、spec 或全局导出文件。
  - 只有当当前会话处于 awaiting_confirmation 状态、finalized_ready=true 且 confirmation_input 精确等于“确认创建”时，才允许写入文件。
  - 只能生成真实本地 Python 工具实现，不得生成不可执行的占位工具、伪实现、仅描述无代码的空壳模块。
  - 不得生成远程 MCP server、外部服务 stub、未在 blueprint 中声明的额外工具，第一版仅支持本地工具实现。
  - 若 blueprint.tool_plan 仅复用现有工具，则必须返回 no_new_tools_required，而不是强行写入空模块。
  - 每个生成的工具必须与其 tool blueprint 中的 purpose、io_schema、implementation_hint 和 risk_level 保持一致，不得擅自扩展能力边界。
  - 工具实现必须可被当前框架发现、导入和调用，至少保证模块结构、函数签名或注册入口可解析。
  - 工具代码应包含简洁中文注释，用于说明边界、输入输出与关键控制流，但不得出现过度解释性注释。
  - created_files 和 generated_tools 必须与真实生成结果一致；部分成功时必须如实返回。
failure_modes:
  - case: not_confirmed
    effect: 禁止写入，保持等待确认状态
  - case: local_tools_not_allowed
    effect: blueprint 需要新工具，但策略不允许生成本地工具
  - case: invalid_tool_blueprint
    effect: 新工具蓝图缺少必要信息，生成出的工具不可运行
  - case: tool_render_failed
    effect: 某个或多个工具模板渲染失败，生成结果不完整
  - case: filesystem_write_failed
    effect: 工具内容已渲染但落盘失败，需返回部分结果
  - case: importability_risk_detected
    effect: 工具文件已生成，但模块命名、导入路径或注册方式存在风险
fallback_strategy:
  - when: not_confirmed
    action: 明确提示只有输入“确认创建”才会开始写入工具文件
  - when: local_tools_not_allowed
    action: 返回策略冲突，要求回到 refine_agent_blueprint 或 plan_agent_tools 调整 tool_policy 或 tool_plan
  - when: invalid_tool_blueprint
    action: 返回具体缺失字段或非法字段，要求 refine tool plan 后重试
  - when: tool_render_failed
    action: 返回具体 tool_name 和失败原因，指导用户修正蓝图后重试
  - when: filesystem_write_failed
    action: 返回已创建文件、失败文件和错误原因，允许后续重试或清理
  - when: importability_risk_detected
    action: 返回高风险项，要求在 validate_generated_agent 前先修正模块命名、导入路径或注册入口
tool_policy:
  audit_logging: true
  sandbox_execution: true
  require_approval_for_write: true
subagent_allowed: false
dependencies:
  - plan_agent_tools
  - finalize_blueprint
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: tool_generation
  role: artifact_subgenerator
  consumes:
    - pending_blueprint
    - confirmation_input
  produces:
    - local_tool_modules
    - created_files
---
Use this skill during the act phase to materialize blueprint.tool_plan.new_tools into real local Python tool modules.

Execution notes:
1. Do not write any tool files before exact confirmation.
2. The only accepted confirmation input is `确认创建`.
3. If the tool plan only reuses existing tools, return `no_new_tools_required` and do not create placeholder files.
4. Generate only the local Python tools explicitly declared in blueprint.tool_plan.new_tools; do not invent extra tools, remote MCP servers, or undeclared capabilities.
5. Each generated tool must be runnable, importable, and aligned with its declared purpose, io_schema, and implementation_hint.
6. On partial failure, return the exact generated tool names, created files, and concrete failure reasons instead of reporting fake success.