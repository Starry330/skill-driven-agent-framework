# 通用 AI Agent 框架技术报告 (Technical Report)

## 1. 概述 (Introduction)
本项目旨在构建一个高泛化性、企业级的通用 AI Agent 框架。通过将底层状态编排与上层业务逻辑彻底解耦，利用“可编译规格 (Soul) + 渐进式技能 (Skills) + 标准化工具 (MCP) + 可观测运行时 (LangGraph)”的组合模式，实现智能体的快速实例化与可靠执行。

---

## 2. 核心模块设计与逻辑 (Core Modules)

### 2.1 基础设施层: LangGraph 运行时
- **设计逻辑**: 采用有状态图 (StateGraph) 模式，将 Agent 的思考、动作、观察和总结抽象为离散的节点 (Nodes) 与有向边 (Edges)。
- **实现方法**: 在 [graph.py](file:///d:/Code/agent-framework/agent_framework/core/graph.py) 中定义 `StateGraph`，通过 `retrieve -> agent -> tools -> summarize` 的拓扑结构实现。
- **关键特性**:
    - **断点续传**: 使用 `MemorySaver` 自动持久化每个步骤的快照。
    - **人在回路 (HITL)**: 通过 `interrupt_before` 参数在敏感操作前挂起执行流。

### 2.2 规格定义层: Soul 引擎
- **设计逻辑**: 将智能体的“灵魂”与代码逻辑分离。通过声明式规格文件定义身份、目标、风格和边界。
- **实现方法**:
    - **模型层**: 在 [models.py](file:///d:/Code/agent-framework/agent_framework/soul/models.py) 中定义 Pydantic 数据模型。
    - **解析层**: 在 [loader.py](file:///d:/Code/agent-framework/agent_framework/soul/loader.py) 中通过正则表达式和 YAML 解析器加载 `.md` 文件中的 Frontmatter 和 Body。
- **应用场景**: 快速切换 Agent 角色（如从“研究助手”切换为“代码审查专家”）。

### 2.3 能力扩展层: Skills 引擎
- **设计逻辑**: 采用“渐进式披露”原则。常驻 Prompt 仅包含技能索引，仅在调用时加载完整说明，以节省 Token 并减少干扰。
- **实现方法**: 在 [registry.py](file:///d:/Code/agent-framework/agent_framework/skills/registry.py) 中扫描目录下的 `SKILL.md` 文件。
- **契约设计**: 技能包包含 YAML 元数据（用于路由）和 Markdown 正文（具体的执行指南）。

### 2.4 记忆与认知系统: PsychMem
- **设计逻辑**: 模拟人类记忆的双轨制。
    - **短期记忆**: 线程级的消息历史。
    - **长效记忆**: 跨线程的语义知识存储。
- **实现方法**: 在 [psych_mem.py](file:///d:/Code/agent-framework/agent_framework/memory/psych_mem.py) 中封装 `LongTermMemory`。
    - **情景记忆 (Episodic)**: 随时间衰减的执行轨迹。
    - **语义记忆 (Semantic)**: 永久保留的核心准则（如架构规范）。

### 2.5 工具接入网关: MCP 集成
- **设计逻辑**: 遵循模型上下文协议 (Model Context Protocol)，统一外部工具的调用接口。
- **实现方法**:
    - **客户端**: 在 [client.py](file:///d:/Code/agent-framework/agent_framework/mcp/client.py) 中实现统一的工具获取与执行接口。
    - **沙箱机制**: 在 [tool_node.py](file:///d:/Code/agent-framework/agent_framework/mcp/tool_node.py) 中通过装饰器模式对所有工具进行安全拦截与日志记录。

---

## 3. 使用方法 (Usage)

### 3.1 框架安装
```bash
pip install -e .
```

### 3.2 实例化流程
1. **编写 Soul**: 在 `examples/` 下创建 `soul.md` 定义角色。
2. **编写技能**: 在 `skills/` 目录下添加特定的 `SKILL.md`。
3. **注册工具**: 使用 `@tool` 装饰器编写函数并注册到 `LocalToolRegistry`。
4. **编译图**: 调用 `create_agent_graph` 生成可运行实例。

### 3.3 交互对话示例
参考 [chat_with_agent.py](file:///d:/Code/agent-framework/chat_with_agent.py)：
- 配置 LLM 参数（Base URL, Model, Extra Body 等）。
- 启动循环输入流。
- 观察控制台输出的“沙箱运行”日志以确认工具调用。

---

## 4. 治理与安全 (Governance)
- **主动压缩 (Auto Compact)**: 在 [compactor.py](file:///d:/Code/agent-framework/agent_framework/memory/compactor.py) 中实现自动摘要，防止上下文溢出引发的逻辑崩溃。
- **执行拦截**: 所有通过 MCP 调用的工具必须通过 `sandbox_exec` 层，支持未来的物理隔离（如 Docker）。
- **HITL 审批**: 在执行图编译时开启中断，实现对敏感 API 或数据库写操作的强制审核。

---

## 5. 结论 (Conclusion)
本框架通过高度解耦的设计，解决了 Agent 开发中的维护难、上下文冗余和安全性差等痛点，为构建稳定、可控的企业级 AI 应用提供了坚实的技术底座。
