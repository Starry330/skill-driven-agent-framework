# Tool Notes

builder agent 可用的工具分为两类：

## 基础工具
- `calculator` - 计算器
- `current_time` - 获取当前时间
- `read_local_file` - 读取本地文件
- `list_directory` - 列出目录内容

## 构建工具（需要确认后才能使用）
- `save_pending_blueprint` - 保存 blueprint 草稿
- `load_pending_blueprint` - 加载 blueprint 草稿
- `clear_pending_blueprint` - 清除 blueprint 草稿
- `refine_agent_blueprint` - 优化 blueprint
- `finalize_blueprint` - 完成 blueprint 校验
- `plan_agent_tools` - 规划工具清单
- `generate_workspace` - 生成工作区文档
- `generate_skills` - 生成技能定义
- `generate_tools` - 生成工具代码
- `generate_spec` - 生成 agent 规格
- `validate_generated_agent` - 验证生成结果
- `generate_agent_scaffold` - 生成完整脚手架
- `confirm_and_generate_agent` - 确认并生成

## 使用规则
- requirements 收集阶段不需要使用工具，runtime 会自动保存。
- 只有当前会话存在待确认 blueprint，且用户精确输入”确认创建”时，才能调用 `confirm_and_generate_agent`。
- 所有写盘工具都不能绕过确认机制提前执行。
