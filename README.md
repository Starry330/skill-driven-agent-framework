# Skill-driven Agent Framework

这是一个基于 LangGraph 的 Python Agent Framework，当前版本已经从单条 demo 工作流重构为更清晰的分层架构：

- `core/` 负责 gateway、session manager、event bus、sub-agent 编排
- `bootstrap/` 负责 workspace 文档装载与 prompt 注入
- `skills/` 负责技能加载、路由、按需激活与 availability 检测
- `tools/` 负责统一 tool schema、policy、executor、approval、audit
- `memory/` 负责 SQLite 持久化、session transcript、summary 与长期记忆
- `mcp/` 负责本地工具层之外的 MCP 适配层
- `workflows/` 只负责 LangGraph 执行图
- `agents/` 提供正式注册的 research / fea agent

## 主要能力

- Workspace/bootstrap 文档体系：`AGENTS.md`、`SOUL.md`、`USER.md`、`TOOLS.md`、`memory/MEMORY.md`
- Skill runtime：候选检索、路由、availability 过滤、按需注入技能正文
- Tool governance：allowlist / denylist、tool whitelist、审批钩子、审计日志、structured error
- Session persistence：SQLite 保存 messages、summary、session_state、events、memories
- Sub-agent 基础能力：独立 session、任务 brief、工具白名单
- 可扩展点：`plugin.yaml`、MCP adapter、tool adapters

## 项目结构

```text
agent_framework/
├── core/
├── bootstrap/
├── config/
├── skills/
├── tools/
├── memory/
├── mcp/
├── workflows/
├── agents/
└── plugins/
tests/
storage/
chat_with_research_agent.py
chat_with_fea_agent.py
chat_with_builder_agent.py
```

## 快速开始

```bash
pip install -e .
python chat_with_research_agent.py
python chat_with_fea_agent.py
python chat_with_builder_agent.py
```

在项目根目录创建 `.env`，可参考 `.env.example`。当前框架默认从项目根目录 `.env` 读取配置，而不是直接从系统环境变量读取。

默认会话和长期记忆使用 `storage/runtime.db`。研究助理中的 `web_search` 为真实可配置 HTTP 工具：未配置 `AGENT_FRAMEWORK_WEB_SEARCH_URL` 时，该 skill 会自动视为 unavailable。

## 测试

```bash
python -m unittest discover -s tests -v
```
