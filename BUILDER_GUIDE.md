# Builder Agent 使用说明

## 定位

`builder_agent` 是当前框架里创建新 agent 的正式入口。
它负责：
- 分阶段收集 requirements
- 根据 requirements 设计和校验结构化 blueprint
- 在确认后生成完整脚手架
- 校验生成结果能否被框架导入和注册

它不是业务问答助手，而是通用 agent 工厂。

## 当前确认机制

builder 采用会话态确认，而不是只靠提示词约束。
只有同时满足以下条件时，才会真正写入文件：
- 当前 session 已存在待确认 blueprint
- `awaiting_confirmation == true`
- 用户本轮输入精确等于 `确认创建`

如果你中途修改需求，旧的 pending blueprint 会被覆盖，并且必须重新确认。

## 典型流程

1. 启动 builder

```bash
python chat_with_builder_agent.py
```

2. 描述你要创建的 agent 需求，例如：

```text
帮我创建一个技术研究助手。
要求：
- 能读取本地文件
- 能做网页搜索
- 输出风格专业、谨慎、简洁
- 默认不要写文件
```

3. builder 会先整理 requirements；如果关键信息不足，会继续追问
4. requirements 足够完整后，builder 才会生成 blueprint 摘要
5. 如果摘要正确，输入：

```text
确认创建
```

6. builder 生成脚手架并返回：
- 新 agent 的 `agent_id`
- 生成目录
- 关键文件列表
- 导入校验结果
- 聊天入口脚本路径

## 自然语言兜底的边界

builder 支持从自然语言中保守提取 requirements，但不会再根据行业词自动套用 preset。
它的行为是：
- 只有当角色、目标和关键能力足够明确时，才会进入 blueprint 设计
- 如果信息不足，就继续追问，不会硬凑一个领域模板
- 即使需求与“面试”“研究”“分析”等场景相关，也只会根据你明确说出的能力生成通用 blueprint

## 生成产物

第一版默认生成完整脚手架：
- `agent_framework/agents/<agent_id>/workspace/AGENTS.md`
- `agent_framework/agents/<agent_id>/workspace/SOUL.md`
- `agent_framework/agents/<agent_id>/workspace/TOOLS.md`
- `agent_framework/agents/<agent_id>/workspace/USER.md`
- `agent_framework/agents/<agent_id>/workspace/memory/MEMORY.md`
- `agent_framework/agents/<agent_id>/skills/<skill_name>/SKILL.md`
- `agent_framework/agents/<agent_id>/spec.py`
- `agent_framework/agents/<agent_id>/__init__.py`
- 可选 `agent_framework/agents/<agent_id>/tools.py`
- `chat_with_<agent_id>_agent.py`

同时会更新：
- `agent_framework/agents/__init__.py`

## 常见情况

### 输入了 `确认创建`，但没有生效

说明当前 session 里没有待确认 blueprint，或者 blueprint 还没有达到 `ready_to_generate`。
这时需要先补充 requirements，或者先完成 blueprint 设计 / refine / finalize。

### 需求修改后为什么要重新确认

因为 builder 会把旧草案覆盖为新的 pending blueprint。任何会影响 blueprint 的修改，都必须重新确认一次。

### 生成失败怎么办

builder 会返回真实失败原因，并保留当前 pending blueprint，方便你继续 refine 后再确认。

## 当前边界

- 第一版只接受精确确认词 `确认创建`
- 第一版不支持同一 session 并行维护多个 pending blueprint
- 第一版只生成本地 Python 工具，不生成远程 MCP server
- builder 不内置任何业务 preset；如果以后需要 preset，应单独设计 preset registry
