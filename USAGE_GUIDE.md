# 使用指南

## 安装

```bash
pip install -e .
```

## 配置

项目默认从仓库根目录 `.env` 读取配置，不直接依赖系统环境变量。可以先复制：

```bash
copy .env.example .env
```

## 核心概念

- `Gateway`
  - 框架统一入口，负责 agent 注册、session 管理和 workflow 调度
- `AgentSpec`
  - 定义 agent 的 workspace、skills、tools、memory policy 和 workflow
- `Bootstrap`
  - 从 workspace 文档构建 prompt 注入和上下文片段
- `Skill`
  - 任务能力单元，不等于 tool
- `Tool`
  - 原子执行能力，受策略、审批和审计约束
- `Session`
  - 短期会话状态，包含 transcript、summary 和 working state
- `Memory`
  - 长期记忆与持久化检索能力

## 目录约定

```text
agent_framework/
├── core/
├── bootstrap/
├── skills/
├── tools/
├── memory/
├── mcp/
├── workflows/
└── agents/
```

每个正式 agent 位于 `agent_framework/agents/<agent_name>/`，通常包含：
- `workspace/`
- `skills/`
- `spec.py`

## Workspace 文档

当前支持的 bootstrap 文档：
- `AGENTS.md`
- `SOUL.md`
- `USER.md`
- `TOOLS.md`
- `memory/MEMORY.md`

## 创建与注册 Agent

标准方式是实现一个 `create_<agent>_agent(...)` 工厂，返回：
- `AgentSpec`
- `list[ToolSpec]`

示例：

```python
from langchain_openai import ChatOpenAI

from agent_framework.agents.research import create_research_agent
from agent_framework.core.gateway import Gateway

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
spec, tools = create_research_agent(llm)

gateway = Gateway()
gateway.register_agent(spec, tools)

response = gateway.run(
    agent_id=spec.agent_id,
    user_input="总结一下这个目录的结构",
)
```

## Tool 与 Skill 的关系

- skill 负责任务级约束、触发条件和行为说明
- tool 负责具体执行
- 一个 skill 可以组合多个 tool
- tool 是否可调用，最终由 `ToolPolicy` 决定

## 聊天入口

通用研究助手：

```bash
python chat_with_research_agent.py
```

FEA 助手：

```bash
python chat_with_fea_agent.py
```

Builder 助手：

```bash
python chat_with_builder_agent.py
```

builder 当前采用严格的会话态确认机制：
- 先收集 requirements，并在信息不足时继续追问
- requirements 完整后再设计并校验 blueprint
- 只有当前会话中存在待确认 blueprint，且状态为 awaiting_confirmation 时，精确输入 `确认创建` 才会真正写入文件
- 如果你修改需求，旧 blueprint 会被覆盖，并且必须重新确认

更完整的 builder 说明见 [`BUILDER_GUIDE.md`](./BUILDER_GUIDE.md)。

## 测试

```bash
python -B -m unittest discover -s tests -v
```

## 不再支持的旧接口

以下旧原型能力已移除，不应继续使用：
- 旧图构建入口
- 旧 soul 加载器
- 旧认知记忆原型接口
- 旧伪沙箱拦截层
- 旧工具节点适配器

当前正式入口是 `Gateway`。
