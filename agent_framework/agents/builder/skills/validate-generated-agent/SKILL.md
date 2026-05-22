---
name: validate-generated-agent
description: Validate that a generated agent package exists, is structurally complete, is importable, and is consistent with the finalized blueprint and generated artifacts. This skill acts as a post-generation quality gate only and must not modify the blueprint, rewrite files, or fabricate successful validation results.
triggers:
  - 校验
  - 验证
  - validate
  - 校验agent
  - 验证agent
required_tools:
  - validate_generated_agent
permissions: []
input_schema:
  type: object
  required:
    - agent_id
  properties:
    agent_id:
      type: string
      description: 需要校验的目标 agent 标识。
    generated_artifacts:
      type: object
      description: 可选的本次生成结果上下文，用于校验实际产物是否完整。
      properties:
        created_files:
          type: array
          items:
            type: string
        workspace_generated:
          type: boolean
        skills_generated:
          type: boolean
        tools_generated:
          type: boolean
        spec_generated:
          type: boolean
    expected_structure:
      type: object
      description: 可选的期望结构说明，通常来自 finalized blueprint。
      properties:
        required_files:
          type: array
          items:
            type: string
        required_skill_names:
          type: array
          items:
            type: string
        required_tool_names:
          type: array
          items:
            type: string
        require_chat_entry:
          type: boolean
        require_export_agent_factory:
          type: boolean
    validation_context:
      type: object
      description: 可选校验上下文，例如是否严格要求与 blueprint 完全一致。
      properties:
        strict_mode:
          type: boolean
        check_importability:
          type: boolean
        check_structure_only:
          type: boolean
output_schema:
  type: object
  required:
    - status
    - validation_messages
    - validation_report
    - next_action
  properties:
    status:
      type: string
      enum:
        - target_not_found
        - validation_passed
        - validation_failed
        - validation_passed_with_warnings
    validation_messages:
      type: array
      description: 面向用户的校验信息列表。
      items:
        type: string
    validation_report:
      type: object
      description: 结构化校验结果，供 orchestrator 或修复阶段直接消费。
      properties:
        target_exists:
          type: boolean
        required_files_ok:
          type: boolean
        structure_ok:
          type: boolean
        importability_ok:
          type: boolean
        skill_package_ok:
          type: boolean
        tool_module_ok:
          type: boolean
        spec_module_ok:
          type: boolean
        package_export_ok:
          type: boolean
        missing_files:
          type: array
          items:
            type: string
        import_errors:
          type: array
          items:
            type: string
        structural_issues:
          type: array
          items:
            type: string
        warnings:
          type: array
          items:
            type: string
    next_action:
      type: string
      enum:
        - inspect_target_agent
        - refine_blueprint_and_regenerate
        - rerun_generation
        - proceed_to_use_agent
decision_logic:
  - if: agent 目录、包或目标标识不存在
    return: target_not_found
  - if: 目标存在，但缺少关键文件、结构不完整、无法导入或关键导出不一致
    return: validation_failed
  - if: 目标存在且核心校验通过，但仍有非阻塞风险项
    return: validation_passed_with_warnings
  - if: 目标存在、结构完整、可导入且关键校验全部通过
    return: validation_passed
constraints:
  - 该 skill 只验证生成结果，不得修改蓝图、回写仓库文件、补写缺失文件或伪造通过结果。
  - 必须优先验证目标 agent 是否真实存在，再进行结构和导入检查。
  - 校验应覆盖存在性、结构完整性、关键文件缺失、模块可导入性、spec 模块可解析性、包导出一致性等核心维度。
  - 若 expected_structure 已提供，应优先按 expected_structure 做一致性校验，而不是仅做最小存在性检查。
  - 当发现问题时，必须返回具体问题，而不是笼统说“校验失败”。
  - 若仅存在非阻塞问题，应使用 validation_passed_with_warnings，而不是误报 validation_failed。
  - 不得把“未检查”伪装成“检查通过”；validation_report 中每个维度都必须反映真实结果。
failure_modes:
  - case: target_not_found
    effect: 无法定位目标 agent，校验无法开始
  - case: missing_required_files
    effect: 生成结果结构不完整，不能视为有效 agent
  - case: import_failure
    effect: 生成结果不可运行，agent 包无法正常导入
  - case: invalid_package_export
    effect: __init__.py 导出与实际实现不一致，使用阶段会失败
  - case: spec_inconsistency
    effect: spec.py 与 skills、tools、workspace 配置不匹配，agent 注册风险高
fallback_strategy:
  - when: target_not_found
    action: 提示目标 agent 不存在，并建议先完成 scaffold generation 或检查 agent_id
  - when: missing_required_files
    action: 返回缺失文件列表，并建议重新执行对应生成步骤
  - when: import_failure
    action: 返回具体导入错误，并建议修正生成结果后重新校验
  - when: invalid_package_export
    action: 返回无效导出项，并建议修复 generate_spec 或相关模块生成逻辑
  - when: spec_inconsistency
    action: 返回不一致项，并建议回到 refine_agent_blueprint 或 rerun_generation
tool_policy:
  audit_logging: true
  sandbox_execution: true
  require_approval_for_write: false
subagent_allowed: false
dependencies: []
availability_checks: []
enabled: true
metadata:
  category: builder
  stage: post_generation_validation
  role: quality_gate
  consumes:
    - agent_id
    - generated_artifacts
    - expected_structure
  produces:
    - validation_report
    - generation_quality_decision
---
Use this skill after scaffold generation or when the user asks for validation.

Execution notes:
1. Call `validate-generated-agent`.
2. Check target existence first, then validate required files, structural completeness, importability, spec consistency, and package exports.
3. Report missing files, import problems, structural issues, warnings, or success signals in a structured way.
4. If validation fails, explain which generation stage likely needs to be rerun instead of giving a vague error.
5. If the last build failed, explicitly explain that the pending blueprint is still kept in session state and can be revised and regenerated.