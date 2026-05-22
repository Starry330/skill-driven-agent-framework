---
name: collect-agent-requirements
description: Collect, normalize, and validate the minimum actionable requirements needed to create a new agent through dialogue. This skill only gathers and structures requirements for downstream blueprint design, and must not generate repository files, code, or fake capabilities.
triggers:
  - 创建agent
  - 新建agent
  - 生成agent
  - 创建智能体
  - builder
  - builder agent
required_tools: []
permissions: []
input_schema:
  type: object
  required:
    - user_request
  properties:
    user_request:
      type: string
      description: 用户当前提出的 agent 创建需求。
    conversation_history:
      type: array
      description: 当前会话中与 agent 需求相关的历史对话，可用于补全上下文。
      items:
        type: object
    existing_requirements:
      type: object
      description: 之前轮次已提取出的需求字段，用于增量补全，而不是重复采集。
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
output_schema:
  type: object
  required:
    - status
    - extracted_requirements
    - missing_fields
    - follow_up_questions
  properties:
    status:
      type: string
      enum:
        - need_more_info
        - ready_for_blueprint
        - conflict_detected
    extracted_requirements:
      type: object
      description: 当前轮次归纳后的结构化需求，供 blueprint 设计阶段直接消费。
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
    missing_fields:
      type: array
      description: 为进入 blueprint 设计仍然缺失的关键字段。
      items:
        type: string
    follow_up_questions:
      type: array
      description: 当信息不足或冲突时，需要向用户继续追问的简洁问题。
      items:
        type: string
    conflicts:
      type: array
      description: 已检测到的冲突信息，例如 role 与 goal 不一致、工具约束互相矛盾。
      items:
        type: string
    collection_summary:
      type: string
      description: 面向后续 blueprint skill 的简洁总结。
decision_logic:
  - if: 无法提取 agent 的核心目标或角色定位
    return: need_more_info
  - if: 已提取到 role、goal、required_skills、user_constraints 等最小建模信息，且不存在明显冲突
    return: ready_for_blueprint
  - if: 用户描述中存在冲突信息，或关键约束彼此矛盾
    return: conflict_detected
constraints:
  - 只能提炼、归纳和补全需求，不直接生成 blueprint 文件、代码或仓库目录。
  - 只输出 requirements 对象；pending requirements 由 runtime 负责保存。
  - 【关键】`required_skills` 和 `required_tools` 必须从用户的**功能描述**中主动推断，不要等待用户提供这些技术细节。用户只需要说"我想让它能生成题目"，系统就应该自动识别需要 `question-generation` skill。
  - 对于没有预定义匹配的功能，可以声明新的工具名称，让 blueprint 设计阶段来设计实现。
  - 优先复用用户原话中的显式要求，只有在用户未说明时才可标记为缺失字段，不得擅自脑补。
  - 追问必须简洁，优先一次性询问最关键的 1 到 3 个缺失点，避免连续碎片化提问。
  - 输出的 extracted_requirements 必须是后续 skill 可直接消费的结构化对象，而不是松散文本。
  - agent_id 若已出现，需归一化为 snake_case；若尚未提供，可暂时留空，不得强行生成。
  - 必须输出 user_message 字段：向用户说明当前收集进度、已确认的需求、或需要追问的问题，语言要自然、口语化，不要重复 JSON 结构。
failure_modes:
  - case: user_request_ambiguous
    effect: 无法确定 agent 的角色、目标或边界，不能进入 blueprint 设计
  - case: conflicting_requirements
    effect: 需求存在冲突，继续建模会导致 blueprint 不稳定
  - case: insufficient_operational_details
    effect: 可描述概念，但无法形成可执行需求对象
fallback_strategy:
  - when: user_request_ambiguous
    action: 输出 missing_fields，并生成最少量 follow_up_questions 追问关键字段
  - when: conflicting_requirements
    action: 输出 conflicts，并要求用户确认优先级或最终取舍
  - when: insufficient_operational_details
    action: 引导用户补充技能、工具、约束、记忆或交互方式
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
  stage: requirements_collection
  produces: requirements_object
  consumes:
    - user_request
    - conversation_history
    - existing_requirements
---
Use this skill to collect and normalize the minimum requirements for creating a new agent.

Execution notes:
1. First extract whatever the user has already specified: role, goal, style, skills, tools, constraints, memory needs, and workflow preferences.
2. Merge the current turn with existing_requirements instead of rebuilding from scratch.
3. If key fields are missing, ask concise follow-up questions focused on the highest-value gaps only.
4. If information conflicts, do not guess; explicitly return conflict_detected and list the conflicts.
5. Do not generate files, code, tools, or blueprint artifacts in this step.
6. 【智能功能推断】不要等待用户提供 `required_skills` 和 `required_tools`，而是从用户的**功能描述**中主动推断：
   - 用户说"生成题目" → 自动添加 `question-generation` skill 和 `question_generator` tool
   - 用户说"评估回答" → 自动添加 `response-evaluation` skill 和 `response_evaluator` tool
   - 用户说"读取文件" → 自动添加 `file-reading` skill 和 `read_local_file`/`list_directory` tools
   - 用户说"导出报告" → 自动添加 `report-export` skill 和 `report_exporter` tool
   - 用户说"记住信息" → 自动添加 `memory-persistence` skill 和 `persistent_memory_store` tool
   - 如果用户描述的功能没有匹配的预定义 skill/tool，可以在 `required_tools` 中声明新工具，让后续的 blueprint 设计阶段来设计实现。
6. Produce a structured requirements object that the next blueprint-design skill can consume directly.
7. Do not ask the user to confirm creation in this step.
8. 接受用户的自然语言描述，从对话中提取需求信息。用户可能用随意的方式描述需求（如"我想创建一个面试助手"），你需要理解意图并提取结构化字段。
9. 如果 requirements 中包含 `[待补充]` 占位符，必须从用户对话中推断或追问来填充这些字段。`[待补充]` 表示系统无法自动提取的信息，需要你来补全。
