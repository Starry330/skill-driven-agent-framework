# 通用 Agent 框架开发规格说明书 (Universal Agent Framework Spec)

## Why
当前大语言模型在处理复杂、长周期任务时面临“上下文溢出”与“逻辑失忆”等瓶颈。为了解决这些问题，本项目旨在构建一个高泛化性、企业级的通用 AI Agent 框架，通过解耦底层状态编排与上层业务逻辑，实现智能体的快速实例化与可靠执行。

## What Changes
本框架将基于 `LangGraph` 构建，并引入以下核心组件：

### 1. 基础设施层 (LangGraph 运行时)
- **状态机编排**: 使用 `StateGraph` 定义全局状态、节点与边。
- **持久化执行**: 集成 `Checkpointer` (Redis/Postgres) 实现断点续传与时间旅行。
- **流式传输**: 支持事件流输出。

### 2. 记忆与认知系统 (Memory System)
- **双层持久化**:
    - **工作记忆 (Short-term)**: 线程级状态管理 (Checkpointer)。
    - **长效记忆 (Long-term)**: 跨线程语义存储 (Store/VectorDB)。
- **认知对齐 (PsychMem)**:
    - **情景记忆**:随时间衰减 (Ebbinghaus)。
    - **语义记忆**: 永久保留 (强类型规则)。
- **主动压缩 (Auto Compact)**: 动态摘要机制，防止上下文溢出。

### 3. 规格定义层 (Soul)
- **soul.md**: 智能体身份与行为控制中心 (Role, Goal, Style, Guardrails)。
- **动态编译**: 解析 `soul.md` 为运行时提示词与约束。

### 4. 能力扩展层 (Skills)
- **SKILL.md**: 标准化技能包 (YAML Metadata + Markdown Body + JSON Schema)。
- **渐进式披露**: 按需加载技能正文，降低 Token 开销。

### 5. 工具接入网关 (MCP)
- **MCP 集成**: 通过 `langchain-mcp-adapters` 接入本地脚本、数据库及 API。
- **安全拦截**: 敏感操作需 HITL (人在回路) 审批。
- **沙箱执行**: 外部技能在 Docker 隔离环境中运行。

### 6. 工作流治理
- **多智能体协作**: Supervisor 模式与 Handoffs 机制。

## Impact
- **Affected Code**: `agent_framework/` (New Package)
- **Dependencies**: `langgraph`, `langchain`, `langchain-core`, `pydantic`, `mcp` (Model Context Protocol SDK).

## ADDED Requirements

### Requirement: Core Runtime
The system SHALL use LangGraph to manage agent state transitions.
The system SHALL support persistence using a pluggable checkpointer.

### Requirement: Soul Definition
The system SHALL parse `soul.md` to configure agent persona and system prompts.
The system SHALL enforce guardrails defined in `soul.md`.

### Requirement: Skill Management
The system SHALL index skills from `SKILL.md` files based on YAML metadata.
The system SHALL dynamically load skill bodies into context only when triggered.

### Requirement: Memory Management
The system SHALL automatically summarize conversation history when token limit is approached.
The system SHALL differentiate between ephemeral (short-term) and semantic (long-term) memory.

### Requirement: MCP Integration
The system SHALL provide a client to connect to MCP servers.
The system SHALL expose MCP tools to the agent runtime.
