# 技术报告

## 当前架构

项目已经从单一 `LangGraph` 原型重构为分层的 `agent_framework`：

- `agent_framework/core/`
  - `gateway.py` 提供统一入口
  - `agent.py` 定义 `AgentSpec` 与运行时上下文
  - `session_manager.py` 负责会话生命周期与存储协调
  - `subagents.py` 负责子代理隔离与结果回传
  - `events.py` 提供事件总线
- `agent_framework/bootstrap/`
  - 负责 workspace 文档装载与 prompt 注入
- `agent_framework/skills/`
  - 负责技能元数据、路由、激活与按需注入
- `agent_framework/tools/`
  - 负责工具注册、策略、审批、执行与审计
- `agent_framework/memory/`
  - 负责 SQLite 会话存储、长期记忆与摘要
- `agent_framework/mcp/`
  - 负责 MCP schema 与适配层
- `agent_framework/workflows/`
  - 仅承载 LangGraph 执行图

## 入口与控制面

正式入口已经收敛到 [`agent_framework/core/gateway.py`](agent_framework/core/gateway.py) 中的 `Gateway`。

调用路径是：

1. 通过 `AgentSpec` 注册 agent
2. `Gateway.run(...)` 创建或恢复 session
3. bootstrap 文档装载与裁剪
4. skill 候选检索、可用性过滤、路由与激活
5. 工具策略校验、执行与审计
6. 会话状态与长期记忆写回

## Workspace 与 Bootstrap

每个正式 agent 都有独立 workspace，当前支持：

- `AGENTS.md`
- `SOUL.md`
- `USER.md`
- `TOOLS.md`
- `memory/MEMORY.md`
- 可选 `IDENTITY.md`、`BOOTSTRAP.md`、`HEARTBEAT.md`

主 agent 与 sub-agent 的注入策略不同：

- 主 agent 注入完整规则与人格约束
- sub-agent 只注入最小任务说明、允许工具摘要和必要规则

## Skill Runtime

Skill 已经不再只是名称与描述。

当前 skill 执行链为：

1. `SkillRegistry` 装载 `SKILL.md`
2. `SkillRouter` 计算候选项与分数
3. `SkillRuntime` 过滤不可用技能
4. 仅对已激活技能注入正文
5. 执行结果与事件写回 session / memory

Research agent 中的 `web_search` 采用“可配置工具，可用性驱动”的方式：

- 已配置 provider 时可用
- 未配置时自动从候选集中剔除

## Tool Governance

旧的伪沙箱拦截实现已删除。

当前工具治理层包含：

- `ToolRegistry`
- `ToolPolicyEngine`
- `ApprovalManager`
- `ToolExecutor`
- `AuditLogger`
- `SandboxAdapter`

默认实现是“受治理的本地执行”，而不是声称提供 OS 级隔离。

## 会话与记忆

SQLite 默认存储路径为 `storage/runtime.db`。

当前存储分层：

- session transcript
- session state
- runtime events
- 长期记忆条目
- 子代理运行记录

bootstrap 文档与长期记忆库已明确分离：

- bootstrap 是静态、可编辑的规范与背景
- memory store 是运行期累积知识

## 示例 Agent

当前正式示例已经迁移到：

- `agent_framework/agents/research/`
- `agent_framework/agents/fea/`

入口脚本：

- `chat_with_agent.py`
- `chat_with_fea_agent.py`

FEA 的 STP 解析与三视图生成实现也已经迁入正式包，不再依赖 `examples/` 目录。
