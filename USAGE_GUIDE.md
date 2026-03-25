# 通用 AI Agent 框架使用指南 (Detailed Usage Guide)

本指南旨在帮助开发者深入了解并使用本通用 AI Agent 框架。框架基于 **LangGraph**，采用了“可编译规格 (Soul) + 渐进式技能 (Skills) + 标准化工具 (MCP)”的解耦架构。

---

## 1. 核心概念

在使用框架之前，请先了解以下四个核心支柱：

- **Soul (灵魂)**: 存储在 `soul.md` 中，定义智能体的角色、长期目标、性格风格和不可逾越的边界（Guardrails）。
- **Skills (技能)**: 存储在 `SKILL.md` 中，是智能体的“操作手册”。包含 YAML 元数据和 Markdown 执行步骤，支持按需加载。
- **Memory (记忆)**: 分为短期工作记忆（线程级）和长效认知记忆（PsychMem），支持情景与语义记忆的隔离。
- **MCP (工具网关)**: 基于模型上下文协议，统一接入本地函数或远程服务工具。

---

## 2. 快速上手步骤

### 第一步：定义智能体灵魂 (`soul.md`)

在你的项目目录（如 `examples/my_agent/`）下创建 `soul.md`。

```markdown
---
role: 资深架构师
goal: 协助用户设计高性能、可扩展的分布式系统。
backstory: 你拥有20年互联网架构经验，擅长高并发和微服务。
style:
  - 专业且严谨
  - 喜欢用对比分析法
guardrails:
  - name: 安全合规
    description: 禁止提供任何涉及攻击或破解的技术建议。
    rules:
      - 禁止输出明文密码。
---
# 角色指令
你现在的身份是资深架构师。在对话中，请始终保持专业态度，并优先考虑系统的稳定性和安全性。
```

### 第二步：编写专家技能 (`SKILL.md`)

技能文件应包含工具的描述和详细的执行指南。

```markdown
---
name: architecture_review
description: 对给定的架构设计方案进行深度评审。
parameters:
  design_doc:
    type: string
    description: 架构设计文档的内容。
metadata:
  category: engineering
---
# 技能执行指南
1. 首先识别方案中的核心组件。
2. 针对每个组件分析其单点故障风险。
3. 检查数据一致性策略。
4. 输出包含“优点”、“潜在风险”和“改进建议”的报告。
```

### 第三步：注册工具

在代码中，你可以通过 `LocalToolRegistry` 注册本地 Python 函数。

```python
from langchain_core.tools import tool
from agent_framework.tools.registry import LocalToolRegistry

@tool
def get_weather(city: str) -> str:
    """获取指定城市的实时天气。"""
    return f"{city} 的天气是晴天，25度。"

registry = LocalToolRegistry()
registry.register_tool(get_weather)
```

### 第四步：初始化框架并运行

```python
from agent_framework.soul.loader import SoulLoader
from agent_framework.skills.registry import SkillRegistry
from agent_framework.memory.psych_mem import PsychMem
from agent_framework.memory.long_term import LongTermMemory
from agent_framework.mcp.client import MCPClient
from agent_framework.core.graph import create_agent_graph

# 1. 加载配置
soul = SoulLoader().load("examples/my_agent/soul.md")
skill_registry = SkillRegistry()
skill_registry.load_directory("examples/my_agent/skills/")

# 2. 初始化记忆与工具
memory = PsychMem(LongTermMemory())
mcp_client = MCPClient(registry) # 使用上一步创建的注册表

# 3. 创建并编译图
# interrupt_before=["tools"] 可开启“人在回路”审批
graph = create_agent_graph(soul, skill_registry, memory, mcp_client, llm)

# 4. 执行对话
config = {"configurable": {"thread_id": "user_1"}}
input_data = {"messages": [("user", "帮我看看这个架构图...")]}

for event in graph.stream(input_data, config):
    print(event)
```

---

## 3. 进阶功能

### 3.1 人在回路 (Human-in-the-Loop)
在调用敏感工具前，框架可以自动挂起执行。
- **开启方式**: 在 `create_agent_graph` 中设置 `interrupt_before=["tools"]`。
- **恢复执行**: 用户审批后，通过 `graph.stream(None, config)` 继续。

### 3.2 主动上下文压缩 (Auto Compact)
框架会自动监控 `AgentState` 中的消息长度。
- 当消息数超过 10 条（默认值，可在 `compactor.py` 修改）时，会自动触发 `summarize` 节点。
- 历史记录会被压缩为摘要并存入 `state["summary"]`，从而释放 Token 空间。

### 3.3 认知对齐记忆 (PsychMem)
- **情景记忆 (Episodic)**: 存储临时任务细节，通过 `memory.add_episodic(content)` 添加。
- **语义记忆 (Semantic)**: 存储永久规则，通过 `memory.add_semantic(content)` 添加。
- 框架在 `retrieve` 阶段会自动将相关记忆注入 Prompt。

---

## 4. 最佳实践

1. **技能粒度**: 保持技能的正文（Markdown 部分）在 500 行以内，过于复杂的逻辑应拆分为多个技能。
2. **Soul 边界**: 在 `soul.md` 中明确定义 `guardrails`，这能显著降低模型的幻觉和违规输出。
3. **环境变量**: 生产环境下，建议将 `LongTermMemory` 替换为基于 Redis 或 Postgres 的实现。
