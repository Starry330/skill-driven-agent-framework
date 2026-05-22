"""Builder agent 的协议化蓝图、工具规划与脚手架生成服务。"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

from agent_framework.builders.models import (
    AgentRequirements,
    BUILDER_CONFIRMATION_PHRASE,
    BUILDER_STATE_KEY,
    AgentBlueprint,
    BuildResult,
    BuilderSessionState,
    NewToolPlanItem,
    SkillBlueprint,
    ToolBlueprint,
    ToolPlan,
    ToolPolicyBlueprint,
    WorkspaceBlueprint,
)
from agent_framework.builders.templates import (
    BUILTIN_TOOL_IMPORTS,
    render_agent_init,
    render_agent_spec,
    render_chat_entry,
    render_skill_markdown,
    render_tools_module,
    render_workspace_documents,
)


class BuilderService:
    """负责把协议化 blueprint 落成真实 agent 包。"""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root)
        self.package_root = self.project_root / "agent_framework"
        self.agents_root = self.package_root / "agents"

    def draft_blueprint(self, payload: str | dict[str, Any] | AgentBlueprint) -> AgentBlueprint:
        if isinstance(payload, AgentBlueprint):
            return payload
        if isinstance(payload, str):
            return self.normalize_blueprint_payload(json.loads(payload))
        return self.normalize_blueprint_payload(payload)

    def draft_requirements(
        self, payload: str | dict[str, Any] | AgentRequirements
    ) -> AgentRequirements:
        if isinstance(payload, AgentRequirements):
            return payload
        if isinstance(payload, str):
            return self.normalize_requirements_payload(json.loads(payload))
        return self.normalize_requirements_payload(payload)

    def _first_non_empty(self, *values: Any) -> str:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    def _slugify_agent_id(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
        normalized = re.sub(r"_+", "_", normalized)
        return normalized or "custom_agent"

    def _skill_name(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
        normalized = re.sub(r"-+", "-", normalized)
        return normalized or "core-skill"

    def _to_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in re.split(r"[，,;；、\n]+", value) if item.strip()]
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            result: list[str] = []
            for item in value:
                text = str(item).strip()
                if text:
                    result.append(text)
            return result
        text = str(value).strip()
        return [text] if text else []

    def _dedupe(self, values: Sequence[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    def _default_workspace_docs(
        self,
        *,
        name: str,
        role: str,
        goal: str,
        tool_names: Sequence[str],
    ) -> WorkspaceBlueprint:
        tool_lines = "\n".join(f"- {tool_name}" for tool_name in tool_names) or "- 待补充"
        return WorkspaceBlueprint(
            agents_md=f"# Agent Rules\n- 你是 {name}。\n- 目标：{goal}",
            soul_md=f"# Role\n{role}\n\n# Goal\n{goal}",
            tools_md=f"# Tools\n{tool_lines}",
            user_md="# User\n- 默认用户画像待补充。",
            memory_md="# Memory\n- 记录长期偏好、任务历史和可复用经验。",
        )

    def normalize_requirements_payload(
        self,
        payload: dict[str, Any] | AgentRequirements,
        existing_requirements: AgentRequirements | None = None,
    ) -> AgentRequirements:
        if isinstance(payload, AgentRequirements):
            return payload

        agent_name = self._first_non_empty(
            payload.get("agent_name"),
            payload.get("name"),
            existing_requirements.agent_name if existing_requirements else "",
        )
        raw_agent_id = self._first_non_empty(
            payload.get("agent_id"),
            payload.get("id"),
            existing_requirements.agent_id if existing_requirements else "",
        )
        agent_id = self._slugify_agent_id(raw_agent_id) if raw_agent_id else ""

        return AgentRequirements(
            agent_name=agent_name,
            agent_id=agent_id,
            role=self._first_non_empty(
                payload.get("role"),
                existing_requirements.role if existing_requirements else "",
            ),
            goal=self._first_non_empty(
                payload.get("goal"),
                existing_requirements.goal if existing_requirements else "",
            ),
            style_constraints=self._dedupe(
                self._to_list(payload.get("style_constraints"))
                or (existing_requirements.style_constraints if existing_requirements else [])
            ),
            required_skills=self._dedupe(
                self._to_list(payload.get("required_skills"))
                or (existing_requirements.required_skills if existing_requirements else [])
            ),
            required_tools=self._dedupe(
                self._to_list(payload.get("required_tools"))
                or (existing_requirements.required_tools if existing_requirements else [])
            ),
            user_constraints=self._dedupe(
                self._to_list(payload.get("user_constraints"))
                or (existing_requirements.user_constraints if existing_requirements else [])
            ),
            memory_requirements=self._dedupe(
                self._to_list(payload.get("memory_requirements"))
                or (existing_requirements.memory_requirements if existing_requirements else [])
            ),
            workflow_preferences=self._dedupe(
                self._to_list(payload.get("workflow_preferences"))
                or (existing_requirements.workflow_preferences if existing_requirements else [])
            ),
        )

    def summarize_requirements(self, requirements: str | dict[str, Any] | AgentRequirements) -> str:
        normalized = self.draft_requirements(requirements)
        return (
            f"agent_name: {normalized.agent_name or '待补充'}\n"
            f"agent_id: {normalized.agent_id or '待补充'}\n"
            f"role: {normalized.role or '待补充'}\n"
            f"goal: {normalized.goal or '待补充'}\n"
            f"required_skills: {', '.join(normalized.required_skills) or '待补充'}\n"
            f"required_tools: {', '.join(normalized.required_tools) or '待补充'}"
        )

    def validate_requirements(
        self, requirements: str | dict[str, Any] | AgentRequirements
    ) -> list[str]:
        normalized = self.draft_requirements(requirements)
        issues: list[str] = []
        if not normalized.role.strip():
            issues.append("role 不能为空。")
        if not normalized.goal.strip():
            issues.append("goal 不能为空。")
        if not normalized.required_skills:
            issues.append("required_skills 至少需要一个。")
        return issues

    def _default_skill_body(self, description: str, required_tools: Sequence[str]) -> str:
        tool_text = ", ".join(required_tools) if required_tools else "declared tools"
        return (
            f"Use {tool_text} to complete this capability. "
            "When available context is insufficient, explain the limitation and ask for the missing information."
        )

    def _required_tools_for_skill(self, skill_name: str) -> list[str]:
        mapping = {
            "question-generation": ["question_generator"],
            "response-evaluation": ["response_evaluator"],
            "memory-persistence": ["persistent_memory_store"],
            "report-export": ["report_exporter"],
            "file-reading": ["read_local_file", "list_directory"],
        }
        return mapping.get(skill_name, [])

    def _skill_description_from_requirement(self, skill_name: str) -> str:
        mapping = {
            "question-generation": "生成问题清单、提问顺序或简短参考答案。",
            "response-evaluation": "对回答或产出进行评估，并给出改进建议。",
            "memory-persistence": "持久化记录历史结果、偏好或长期状态。",
            "report-export": "把分析结果或阶段性结论导出为文档。",
            "file-reading": "读取和浏览本地文件。",
        }
        return mapping.get(skill_name, skill_name)

    def _skill_triggers_from_requirement(self, skill_name: str) -> list[str]:
        mapping = {
            "question-generation": ["生成题目", "题库", "提问"],
            "response-evaluation": ["评估", "反馈", "建议"],
            "memory-persistence": ["记录", "记住", "回顾"],
            "report-export": ["导出报告", "生成报告"],
            "file-reading": ["读取文件", "浏览目录"],
        }
        return mapping.get(skill_name, [])

    def _generic_tool_blueprint(self, name: str) -> ToolBlueprint | None:
        if name == "persistent_memory_store":
            return ToolBlueprint(
                name=name,
                description="将结构化记录持久化到本地 SQLite，并支持最近记录查询。",
                reuse_existing=False,
                reason="用户明确要求持久记忆。",
                io_schema={
                    "input": {"action": "string", "key": "string", "value": "string"},
                    "output": {"result": "string"},
                },
                risk_level="medium",
                side_effect_level="medium",
                implementation_code=(
                    "@tool\n"
                    "def persistent_memory_store(action: str, key: str = '', value: str = '') -> str:\n"
                    '    """Persist simple key/value notes into a local SQLite database."""\n\n'
                    "    import sqlite3\n"
                    "    from pathlib import Path\n\n"
                    "    db_path = Path(__file__).resolve().parent / 'workspace' / 'memory' / 'memory.db'\n"
                    "    db_path.parent.mkdir(parents=True, exist_ok=True)\n"
                    "    conn = sqlite3.connect(db_path)\n"
                    "    try:\n"
                    "        conn.execute('CREATE TABLE IF NOT EXISTS memory_store (key TEXT, value TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')\n"
                    "        if action == 'save':\n"
                    "            conn.execute('INSERT INTO memory_store (key, value) VALUES (?, ?)', (key, value))\n"
                    "            conn.commit()\n"
                    "            return 'saved'\n"
                    "        rows = conn.execute('SELECT key, value FROM memory_store ORDER BY rowid DESC LIMIT 10').fetchall()\n"
                    "        return '\\n'.join(f'{row[0]}: {row[1]}' for row in rows) or 'no_records'\n"
                    "    finally:\n"
                    "        conn.close()\n"
                ),
            )
        if name == "report_exporter":
            return ToolBlueprint(
                name=name,
                description="把 Markdown 报告导出到本地 workspace。",
                reuse_existing=False,
                reason="用户明确要求报告导出。",
                io_schema={"input": {"report_markdown": "string"}, "output": {"path": "string"}},
                risk_level="medium",
                side_effect_level="medium",
                implementation_code=(
                    "@tool\n"
                    "def report_exporter(report_markdown: str) -> str:\n"
                    '    """Export markdown content into workspace/memory/reports."""\n\n'
                    "    from datetime import datetime\n"
                    "    from pathlib import Path\n\n"
                    "    reports_dir = Path(__file__).resolve().parent / 'workspace' / 'memory' / 'reports'\n"
                    "    reports_dir.mkdir(parents=True, exist_ok=True)\n"
                    "    path = reports_dir / f'report_{datetime.now().strftime(\"%Y%m%d_%H%M%S\")}.md'\n"
                    "    path.write_text(report_markdown, encoding='utf-8')\n"
                    "    return str(path)\n"
                ),
            )
        if name == "question_generator":
            return ToolBlueprint(
                name=name,
                description="根据主题生成问题清单和简短参考答案。",
                reuse_existing=False,
                reason="用户明确要求题目生成或题库能力。",
                io_schema={"input": {"topic": "string"}, "output": {"questions": "string"}},
                risk_level="low",
                implementation_code=(
                    "@tool\n"
                    "def question_generator(topic: str) -> str:\n"
                    '    """Return a short list of questions and answer hints."""\n\n'
                    "    return (\n"
                    "        f'主题: {topic}\\n'\n"
                    "        '1. 请说明该主题中的核心概念。\\n'\n"
                    "        '参考思路: 定义 -> 原理 -> 适用场景。\\n'\n"
                    "        '2. 请结合项目经验说明你如何落地。\\n'\n"
                    "        '参考思路: 背景 -> 方案 -> 权衡 -> 结果。'\n"
                    "    )\n"
                ),
            )
        if name == "response_evaluator":
            return ToolBlueprint(
                name=name,
                description="对回答或产出做规则化评估，并给出改进建议。",
                reuse_existing=False,
                reason="用户明确要求评估或反馈能力。",
                io_schema={"input": {"content": "string"}, "output": {"evaluation": "string"}},
                risk_level="low",
                implementation_code=(
                    "@tool\n"
                    "def response_evaluator(content: str) -> str:\n"
                    '    """Return a simple rubric-based evaluation."""\n\n'
                    "    score = min(max(len(content.strip()) // 50 + 1, 1), 5)\n"
                    "    return (\n"
                    "        f'评分: {score}/5\\n'\n"
                    "        '优点: 内容具备一定信息量。\\n'\n"
                    "        '建议: 补充背景、权衡过程和量化结果。'\n"
                    "    )\n"
                ),
            )
        return None

    def _normalize_tool_payload(self, payload: dict[str, Any]) -> ToolBlueprint:
        name = self._first_non_empty(
            payload.get("name"), payload.get("tool_name"), payload.get("tool_id")
        )
        if not name:
            raise ValueError("tool 名称不能为空")
        reuse_existing = bool(
            payload.get("reuse_existing", payload.get("existing_tool_name") is not None)
        )
        tool = ToolBlueprint(
            name=name,
            description=self._first_non_empty(payload.get("description"), f"{name} tool"),
            reuse_existing=reuse_existing,
            existing_tool_name=self._first_non_empty(payload.get("existing_tool_name")) or None,
            reason=self._first_non_empty(payload.get("reason"), "来自 builder 需求抽取。"),
            io_schema=payload.get("io_schema")
            if isinstance(payload.get("io_schema"), dict)
            else {},
            risk_level=self._first_non_empty(payload.get("risk_level"), "low"),
            implementation_code=self._first_non_empty(payload.get("implementation_code")),
            side_effect_level=self._first_non_empty(payload.get("side_effect_level"), "low"),
            workspace_scope=self._first_non_empty(payload.get("workspace_scope"), "workspace"),
            timeout_seconds=int(payload.get("timeout_seconds", 30) or 30),
        )
        if not tool.reuse_existing and not tool.implementation_code:
            generic = self._generic_tool_blueprint(tool.name)
            if generic is not None:
                tool = generic.model_copy(
                    update={
                        "description": tool.description or generic.description,
                        "reason": tool.reason or generic.reason,
                        "io_schema": tool.io_schema or generic.io_schema,
                        "risk_level": tool.risk_level or generic.risk_level,
                    }
                )
        return tool

    def _normalize_skill_payload(self, payload: dict[str, Any]) -> SkillBlueprint:
        raw_name = self._first_non_empty(
            payload.get("name"), payload.get("skill_name"), payload.get("skill_id")
        )
        if not raw_name:
            raise ValueError("skill 名称不能为空")
        required_tools = self._to_list(payload.get("required_tools"))
        description = self._first_non_empty(payload.get("description"), raw_name)
        return SkillBlueprint(
            name=self._skill_name(raw_name),
            description=description,
            body=self._first_non_empty(
                payload.get("body"), self._default_skill_body(description, required_tools)
            ),
            triggers=self._to_list(payload.get("triggers")),
            required_tools=required_tools,
            permissions=self._to_list(payload.get("permissions")),
            input_schema=payload.get("input_schema")
            if isinstance(payload.get("input_schema"), dict)
            else {"type": "object"},
            output_schema=payload.get("output_schema")
            if isinstance(payload.get("output_schema"), dict)
            else {"type": "string"},
            decision_logic=payload.get("decision_logic")
            if isinstance(payload.get("decision_logic"), list)
            else [{"else": "use_declared_tools"}],
            constraints=self._to_list(payload.get("constraints")),
            failure_modes=payload.get("failure_modes")
            if isinstance(payload.get("failure_modes"), list)
            else [],
            fallback_strategy=payload.get("fallback_strategy")
            if isinstance(payload.get("fallback_strategy"), list)
            else [],
            tool_policy=payload.get("tool_policy")
            if isinstance(payload.get("tool_policy"), dict)
            else {},
            dependencies=self._to_list(payload.get("dependencies")),
            availability_checks=self._to_list(payload.get("availability_checks")),
            subagent_allowed=bool(payload.get("subagent_allowed", False)),
            enabled=bool(payload.get("enabled", True)),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )

    def _default_skill_from_goal(self, goal: str, tool_names: Sequence[str]) -> SkillBlueprint:
        required_tools = list(tool_names[:3])
        return SkillBlueprint(
            name="core-assistance",
            description="执行该 agent 的核心任务。",
            body=self._default_skill_body(goal, required_tools),
            required_tools=required_tools,
            input_schema={"type": "object"},
            output_schema={"type": "string"},
            decision_logic=[{"else": "use_declared_tools"}],
            constraints=["优先完成用户给出的主目标。"],
        )

    def _merge_named_items(self, base_items: Sequence[Any], new_items: Sequence[Any]) -> list[Any]:
        ordered: list[Any] = []
        seen: dict[str, int] = {}
        for item in base_items:
            ordered.append(item)
            seen[getattr(item, "name")] = len(ordered) - 1
        for item in new_items:
            name = getattr(item, "name")
            if name in seen:
                ordered[seen[name]] = item
            else:
                seen[name] = len(ordered)
                ordered.append(item)
        return ordered

    def infer_requirements_from_text(
        self,
        *,
        user_input: str,
        model_text: str,
        existing_requirements: AgentRequirements | None = None,
    ) -> AgentRequirements | None:
        """从用户输入中推断创建 agent 的需求。

        设计思路：
        1. 只要检测到创建意图，就返回基本需求对象（允许信息不完整）
        2. 通过关键词匹配快速提取已知信息
        3. 对于无法提取的字段，生成占位符，让 LLM 通过 collect-agent-requirements skill 补全
        """
        text = "\n".join(part.strip() for part in (user_input, model_text) if part and part.strip())
        if not text:
            return None

        # 检测创建意图
        intent_tokens = (
            "创建", "生成", "设计", "蓝图", "agent", "助手", "智能体",
            "技能", "工具", "模式", "能力", "需要", "支持",
            "机器人", "bot", "做一个", "帮我做", "开发",
        )
        if not any(token in user_input for token in intent_tokens):
            return None

        # 提取 agent 名称
        explicit_name = ""
        for pattern in (
            r"创建一个(?P<name>[^，。\n]+?)(?:agent|助手|智能体|机器人)",
            r"我想要(?:一个)?(?P<name>[^，。\n]+?)(?:agent|助手|智能体|机器人)",
            r"我想创建(?:一个)?(?P<name>[^，。\n]+?)(?:agent|助手|智能体|机器人)",
            r"(?:创建|设计|生成|做一个|帮我做)(?:一个)?(?P<name>[^，。\n]+?)(?:的)?(?:agent|助手|智能体|机器人)",
            r"(?:做一个|帮我做)(?P<name>[^，。\n]+?)(?:机器人|bot)",
        ):
            match = re.search(pattern, user_input)
            if match:
                explicit_name = match.group("name").strip()
                break

        resolved_name = explicit_name or (
            existing_requirements.agent_name if existing_requirements is not None else ""
        )
        agent_id = self._slugify_agent_id(resolved_name) if resolved_name else ""

        # 提取风格约束
        style_constraints: list[str] = []
        for keyword, style in (
            ("专业", "保持专业语气"),
            ("严谨", "保持严谨"),
            ("谨慎", "谨慎给出结论"),
            ("简洁", "输出简洁"),
        ):
            if keyword in text and style not in style_constraints:
                style_constraints.append(style)

        # 通过关键词推断 skills 和 tools
        required_skills: list[str] = []
        required_tools: list[str] = []
        self._extract_skills_and_tools(text, required_skills, required_tools)

        # 尝试提取 goal
        explicit_goal = self._extract_goal(text)

        # 尝试提取 role
        explicit_role = self._extract_role(text, existing_requirements)

        # 合并已有的 requirements
        if existing_requirements is not None:
            resolved_name = resolved_name or existing_requirements.agent_name
            style_constraints = style_constraints or list(existing_requirements.style_constraints)
            required_skills = self._dedupe(
                required_skills or list(existing_requirements.required_skills)
            )
            required_tools = self._dedupe(
                required_tools or list(existing_requirements.required_tools)
            )
            explicit_goal = explicit_goal or existing_requirements.goal
            explicit_role = explicit_role or existing_requirements.role

        # 生成 goal 和 role（如果无法提取，则生成占位符让 LLM 补全）
        goal = explicit_goal or self._generate_goal_placeholder(resolved_name, required_skills)
        role = explicit_role or self._generate_role_placeholder(resolved_name, required_skills)

        requirements_payload = {
            "agent_name": resolved_name,
            "agent_id": agent_id,
            "role": role,
            "goal": goal,
            "style_constraints": style_constraints,
            "required_skills": required_skills,
            "required_tools": required_tools,
        }
        return self.normalize_requirements_payload(requirements_payload, existing_requirements)

    def _extract_skills_and_tools(
        self,
        text: str,
        required_skills: list[str],
        required_tools: list[str],
    ) -> None:
        """从文本中提取 skills 和 tools。

        设计原则：
        1. 用户只需要描述功能（如"生成题目"），系统自动匹配 skill/tool
        2. 关键词匹配覆盖常见的功能描述方式
        3. 允许一个功能对应多个关键词变体
        """
        skill_tool_mapping = {
            "question-generation": {
                "keywords": (
                    "提问", "追问", "问题生成", "生成题目", "题库", "问题列表",
                    "面试题", "出题", "考题", "测试题", "练习题", "发问",
                ),
                "tools": ["question_generator"],
            },
            "response-evaluation": {
                "keywords": (
                    "评估", "反馈", "建议", "打分", "改进", "评分",
                    "评价", "点评", "批改", "审核", "检查",
                ),
                "tools": ["response_evaluator"],
            },
            "memory-persistence": {
                "keywords": (
                    "持久记忆", "长期记忆", "SQLite", "本地数据库", "跨会话",
                    "记住", "存储", "保存记录", "历史记录", "记忆",
                ),
                "tools": ["persistent_memory_store"],
            },
            "report-export": {
                "keywords": (
                    "报告", "导出", "Markdown",
                    "生成报告", "输出报告", "导出文件", "生成文档",
                ),
                "tools": ["report_exporter"],
            },
            "file-reading": {
                "keywords": (
                    "文件", "读取文件", "本地文件",
                    "读取", "浏览目录", "打开文件", "查看文件",
                ),
                "tools": ["read_local_file", "list_directory"],
            },
            "conversation": {
                "keywords": (
                    "对话", "聊天", "交流", "沟通", "问答",
                    "交谈", "互动", "交互",
                ),
                "tools": ["conversation_handler"],
            },
            "information-retrieval": {
                "keywords": (
                    "搜索", "查询", "检索", "查找",
                    "搜索网页", "网络搜索", "查找资料",
                ),
                "tools": ["search_engine"],
            },
        }

        for skill_name, config in skill_tool_mapping.items():
            if any(token in text for token in config["keywords"]):
                if skill_name not in required_skills:
                    required_skills.append(skill_name)
                for tool in config["tools"]:
                    if tool not in required_tools:
                        required_tools.append(tool)

    def _extract_goal(self, text: str) -> str:
        """从文本中提取 goal。"""
        # 尝试显式的 goal 关键词
        goal_patterns = [
            r"(?:目标|用途|主要用于|主要功能|希望它)([^。\n]+)",
            r"(?:用来|用于|帮助用户)([^。\n]+)",
            r"(?:能够|可以)([^。\n]+)",
        ]
        for pattern in goal_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip("：:，,。 ")
        return ""

    def _extract_role(
        self,
        text: str,
        existing_requirements: AgentRequirements | None = None,
    ) -> str:
        """从文本中提取 role。"""
        role_fragments: list[str] = []

        # 基于关键词推断 role
        role_keywords = {
            ("扮演", "模拟"): "根据用户需求切换工作模式的助手",
            ("评估", "反馈", "建议"): "提供评估与反馈的助手",
            ("读取文件", "本地文件"): "可结合本地文件上下文的助手",
            ("面试", "提问", "问答"): "模拟面试与问答的助手",
            ("分析", "解析", "研究"): "提供分析与研究能力的助手",
            ("生成", "创建", "编写"): "能够生成和创建内容的助手",
            ("搜索", "查询", "检索"): "提供信息检索能力的助手",
            ("记录", "存储", "记忆"): "提供信息存储与记忆能力的助手",
        }

        for keywords, role_desc in role_keywords.items():
            if any(token in text for token in keywords):
                role_fragments.append(role_desc)

        explicit_role = "；".join(dict.fromkeys(role_fragments))
        if not explicit_role:
            explicit_role = existing_requirements.role if existing_requirements is not None else ""
        return explicit_role

    def _generate_goal_placeholder(
        self,
        agent_name: str,
        required_skills: list[str],
    ) -> str:
        """当无法提取 goal 时，生成占位符让 LLM 补全。"""
        if agent_name:
            return f"[待补充] {agent_name}的核心目标"
        return "[待补充] agent 的核心目标"

    def _generate_role_placeholder(
        self,
        agent_name: str,
        required_skills: list[str],
    ) -> str:
        """当无法提取 role 时，生成占位符让 LLM 补全。"""
        if agent_name:
            return f"[待补充] {agent_name}的角色定位"
        return "[待补充] agent 的角色定位"

    def design_blueprint_from_requirements(
        self,
        requirements: str | dict[str, Any] | AgentRequirements,
        existing_blueprint: AgentBlueprint | None = None,
    ) -> AgentBlueprint:
        normalized = self.draft_requirements(requirements)
        tool_payloads: list[dict[str, Any]] = []
        declared_tool_names: set[str] = set()

        for tool_name in normalized.required_tools:
            if tool_name in declared_tool_names:
                continue
            if tool_name in BUILTIN_TOOL_IMPORTS:
                tool_payloads.append(
                    {
                        "name": tool_name,
                        "reuse_existing": True,
                        "existing_tool_name": tool_name,
                    }
                )
            else:
                tool_payloads.append({"name": tool_name, "reuse_existing": False})
            declared_tool_names.add(tool_name)

        skill_payloads: list[dict[str, Any]] = []
        for skill_name in normalized.required_skills:
            required_tools = [
                tool_name
                for tool_name in normalized.required_tools
                if tool_name in self._required_tools_for_skill(skill_name)
            ]
            if not required_tools and normalized.required_tools:
                required_tools = list(normalized.required_tools[:1])
            skill_payloads.append(
                {
                    "name": skill_name,
                    "description": self._skill_description_from_requirement(skill_name),
                    "required_tools": required_tools,
                    "triggers": self._skill_triggers_from_requirement(skill_name),
                    "constraints": normalized.user_constraints,
                }
            )

        blueprint_payload = {
            "agent_id": normalized.agent_id or self._slugify_agent_id(normalized.agent_name),
            "name": normalized.agent_name,
            "role": normalized.role,
            "goal": normalized.goal,
            "style_constraints": normalized.style_constraints,
            "skills": skill_payloads,
            "tool_plan": tool_payloads,
            "memory_namespaces": (
                ["semantic", "episodic", "user_memory", "task_memory", "tool_notes"]
                if normalized.memory_requirements
                else ["semantic", "episodic", "user_memory", "task_memory"]
            ),
        }
        return self.normalize_blueprint_payload(blueprint_payload, existing_blueprint)

    def normalize_blueprint_payload(
        self,
        payload: dict[str, Any] | AgentBlueprint,
        existing_blueprint: AgentBlueprint | None = None,
    ) -> AgentBlueprint:
        if isinstance(payload, AgentBlueprint):
            return payload

        raw_name = self._first_non_empty(
            payload.get("name"), payload.get("agent_name"), payload.get("title")
        )
        name = raw_name or (existing_blueprint.name if existing_blueprint else "")

        raw_agent_id = self._first_non_empty(payload.get("agent_id"), payload.get("id"))
        if raw_agent_id:
            agent_id = self._slugify_agent_id(raw_agent_id)
        elif existing_blueprint is not None:
            agent_id = existing_blueprint.agent_id
        else:
            agent_id = self._slugify_agent_id(name) if name else ""

        role = self._first_non_empty(
            payload.get("role"),
            existing_blueprint.role if existing_blueprint else "",
        )
        goal = self._first_non_empty(
            payload.get("goal"),
            existing_blueprint.goal if existing_blueprint else "",
        )

        style_constraints = self._to_list(payload.get("style_constraints")) or (
            list(existing_blueprint.style_constraints) if existing_blueprint else []
        )

        raw_tools = (
            payload.get("tool_plan")
            if payload.get("tool_plan") is not None
            else payload.get("tools")
        )
        tool_plan = (
            [self._normalize_tool_payload(item) for item in raw_tools]
            if isinstance(raw_tools, list)
            else []
        )
        if not tool_plan and existing_blueprint is not None:
            tool_plan = list(existing_blueprint.tool_plan)

        raw_skills = payload.get("skills")
        skills = (
            [self._normalize_skill_payload(item) for item in raw_skills]
            if isinstance(raw_skills, list)
            else []
        )
        if not skills:
            if existing_blueprint is not None and existing_blueprint.skills:
                skills = list(existing_blueprint.skills)
            else:
                skills = []

        raw_workspace = (
            payload.get("workspace_docs") if isinstance(payload.get("workspace_docs"), dict) else {}
        )
        if raw_workspace:
            workspace_docs = WorkspaceBlueprint.model_validate(raw_workspace)
        elif existing_blueprint is not None:
            workspace_docs = existing_blueprint.workspace_docs
        else:
            workspace_docs = self._default_workspace_docs(
                name=name or "待补充 Agent",
                role=role or "待补充角色",
                goal=goal or "待补充目标",
                tool_names=[tool.existing_tool_name or tool.name for tool in tool_plan],
            )

        raw_tool_policy = (
            payload.get("tool_policy") if isinstance(payload.get("tool_policy"), dict) else {}
        )
        allowlist = self._to_list(raw_tool_policy.get("allowlist")) or [
            tool.existing_tool_name or tool.name for tool in tool_plan
        ]
        denylist = self._to_list(raw_tool_policy.get("denylist"))
        skill_tool_overrides = (
            raw_tool_policy.get("skill_tool_overrides")
            if isinstance(raw_tool_policy.get("skill_tool_overrides"), dict)
            else {}
        )
        if not skill_tool_overrides:
            skill_tool_overrides = {
                skill.name: [
                    tool_name for tool_name in skill.required_tools if tool_name in allowlist
                ]
                for skill in skills
                if skill.required_tools
            }
        tool_policy = ToolPolicyBlueprint(
            allowlist=allowlist,
            denylist=denylist,
            skill_tool_overrides={
                key: self._to_list(value) for key, value in skill_tool_overrides.items()
            },
            approval_required_for=self._to_list(raw_tool_policy.get("approval_required_for"))
            or ["high", "critical"],
        )

        memory_namespaces = self._to_list(payload.get("memory_namespaces")) or (
            list(existing_blueprint.memory_namespaces)
            if existing_blueprint
            else ["semantic", "episodic", "user_memory", "task_memory"]
        )

        return AgentBlueprint(
            agent_id=agent_id,
            name=name,
            role=role,
            goal=goal,
            style_constraints=style_constraints,
            workspace_docs=workspace_docs,
            skills=skills,
            tool_plan=tool_plan,
            tool_policy=tool_policy,
            memory_namespaces=memory_namespaces,
            workflow_name=self._first_non_empty(
                payload.get("workflow_name"),
                existing_blueprint.workflow_name if existing_blueprint else "default",
            ),
            create_chat_entry=bool(
                payload.get(
                    "create_chat_entry",
                    existing_blueprint.create_chat_entry if existing_blueprint else True,
                )
            ),
            export_agent_factory=bool(
                payload.get(
                    "export_agent_factory",
                    existing_blueprint.export_agent_factory if existing_blueprint else True,
                )
            ),
            metadata=payload.get("metadata")
            if isinstance(payload.get("metadata"), dict)
            else (existing_blueprint.metadata if existing_blueprint else {}),
        )

    def refine_blueprint(
        self,
        base_blueprint: str | dict[str, Any] | AgentBlueprint,
        refinement: str | dict[str, Any] | AgentBlueprint,
    ) -> AgentBlueprint:
        base = self.draft_blueprint(base_blueprint)
        update = self.normalize_blueprint_payload(
            json.loads(refinement) if isinstance(refinement, str) else refinement,
            base,
        )
        return AgentBlueprint(
            agent_id=update.agent_id or base.agent_id,
            name=update.name or base.name,
            role=update.role or base.role,
            goal=update.goal or base.goal,
            style_constraints=list(
                dict.fromkeys([*base.style_constraints, *update.style_constraints])
            ),
            workspace_docs=WorkspaceBlueprint(
                agents_md=update.workspace_docs.agents_md or base.workspace_docs.agents_md,
                soul_md=update.workspace_docs.soul_md or base.workspace_docs.soul_md,
                tools_md=update.workspace_docs.tools_md or base.workspace_docs.tools_md,
                user_md=update.workspace_docs.user_md or base.workspace_docs.user_md,
                memory_md=update.workspace_docs.memory_md or base.workspace_docs.memory_md,
            ),
            skills=self._merge_named_items(base.skills, update.skills),
            tool_plan=self._merge_named_items(base.tool_plan, update.tool_plan),
            tool_policy=ToolPolicyBlueprint(
                allowlist=list(
                    dict.fromkeys([*base.tool_policy.allowlist, *update.tool_policy.allowlist])
                ),
                denylist=list(
                    dict.fromkeys([*base.tool_policy.denylist, *update.tool_policy.denylist])
                ),
                skill_tool_overrides={
                    **base.tool_policy.skill_tool_overrides,
                    **update.tool_policy.skill_tool_overrides,
                },
                approval_required_for=list(
                    dict.fromkeys(
                        [
                            *base.tool_policy.approval_required_for,
                            *update.tool_policy.approval_required_for,
                        ]
                    )
                ),
            ),
            memory_namespaces=list(
                dict.fromkeys([*base.memory_namespaces, *update.memory_namespaces])
            ),
            workflow_name=update.workflow_name or base.workflow_name,
            create_chat_entry=update.create_chat_entry,
            export_agent_factory=update.export_agent_factory,
            metadata={**base.metadata, **update.metadata},
        )

    def build_tool_plan(self, blueprint: str | dict[str, Any] | AgentBlueprint) -> ToolPlan:
        normalized = self.draft_blueprint(blueprint)
        reuse_tools = sorted(
            {
                tool.existing_tool_name or tool.name
                for tool in normalized.tool_plan
                if tool.reuse_existing
            }
        )
        new_tools = [
            NewToolPlanItem(
                name=tool.name,
                reason=tool.reason,
                io_schema=tool.io_schema,
                risk_level=tool.risk_level,
            )
            for tool in normalized.tool_plan
            if not tool.reuse_existing
        ]
        return ToolPlan(reuse_tools=reuse_tools, new_tools=new_tools)

    def validate_blueprint(self, blueprint: str | dict[str, Any] | AgentBlueprint) -> list[str]:
        normalized = self.draft_blueprint(blueprint)
        issues: list[str] = []
        if not re.fullmatch(r"[a-z][a-z0-9_]*", normalized.agent_id):
            issues.append("agent_id 必须使用 snake_case。")
        if not normalized.name.strip():
            issues.append("name 不能为空。")
        if not normalized.role.strip():
            issues.append("role 不能为空。")
        if not normalized.goal.strip():
            issues.append("goal 不能为空。")
        if not normalized.skills:
            issues.append("至少需要一个 skill。")
        if (self.agents_root / normalized.agent_id).exists():
            issues.append(f"agent_id 已存在：{normalized.agent_id}")

        declared_tools = {tool.existing_tool_name or tool.name for tool in normalized.tool_plan}
        for tool in normalized.tool_plan:
            if not tool.reuse_existing and not tool.implementation_code.strip():
                issues.append(f"自定义工具缺少 implementation_code：{tool.name}")
        for skill in normalized.skills:
            for required in skill.required_tools:
                if required not in declared_tools and required not in BUILTIN_TOOL_IMPORTS:
                    issues.append(f"skill {skill.name} 依赖了未声明工具：{required}")
        return issues

    def finalize_blueprint(
        self, blueprint: str | dict[str, Any] | AgentBlueprint
    ) -> dict[str, Any]:
        normalized = self.draft_blueprint(blueprint)
        issues = self.validate_blueprint(normalized)
        if not issues:
            return {
                "status": "ready_to_generate",
                "message": "blueprint 已达到可生成状态。",
                "issues": [],
            }
        status = (
            "conflict_detected"
            if any("已存在" in issue or "snake_case" in issue for issue in issues)
            else "need_more_info"
        )
        return {"status": status, "message": "blueprint 仍需补充或修正。", "issues": issues}

    def _load_builder_state(self, working_state: dict[str, Any]) -> BuilderSessionState:
        raw_state = working_state.get(BUILDER_STATE_KEY)
        if not isinstance(raw_state, dict):
            return BuilderSessionState()
        return BuilderSessionState.model_validate(raw_state)

    def _merge_builder_state(
        self, working_state: dict[str, Any], builder_state: BuilderSessionState
    ) -> dict[str, Any]:
        next_state = dict(working_state)
        next_state[BUILDER_STATE_KEY] = builder_state.model_dump(mode="json")
        return next_state

    def summarize_blueprint(self, blueprint: str | dict[str, Any] | AgentBlueprint) -> str:
        normalized = self.draft_blueprint(blueprint)
        skill_names = ", ".join(skill.name for skill in normalized.skills) or "无"
        tool_names = (
            ", ".join(tool.existing_tool_name or tool.name for tool in normalized.tool_plan) or "无"
        )
        return (
            f"agent_id: {normalized.agent_id}\n"
            f"name: {normalized.name}\n"
            f"role: {normalized.role}\n"
            f"goal: {normalized.goal}\n"
            f"skills: {skill_names}\n"
            f"tools: {tool_names}"
        )

    def render_confirmation_prompt(
        self,
        *,
        summary: str,
        finalization_status: str,
        message: str,
        awaiting_confirmation: bool,
    ) -> str:
        if awaiting_confirmation and finalization_status == "ready_to_generate":
            return (
                f"{message}\n\n{summary}\n\n"
                f'以上是为你设计的 blueprint 摘要。确认无误后，输入"{BUILDER_CONFIRMATION_PHRASE}"即可生成完整脚手架。'
            )
        return f"{message}\n\n{summary}\n\n还有些信息需要补充或修正，请告诉我具体需要调整什么。"

    def store_pending_requirements(
        self,
        working_state: dict[str, Any],
        requirements: str | dict[str, Any] | AgentRequirements,
    ) -> dict[str, Any]:
        normalized = self.draft_requirements(requirements)
        builder_state = self._load_builder_state(working_state)
        builder_state.pending_requirements = normalized.model_dump(mode="json")
        builder_state.requirements_summary = self.summarize_requirements(normalized)
        builder_state.pending_blueprint = None
        builder_state.pending_blueprint_summary = ""
        builder_state.tool_plan = {}
        builder_state.finalization_status = "draft"
        builder_state.awaiting_confirmation = False
        builder_state.stage = "requirements_collected"
        builder_state.last_build_result = {
            "status": "requirements_pending",
            "message": "已更新待确认需求。",
        }
        return self._merge_builder_state(working_state, builder_state)

    def load_pending_requirements(self, working_state: dict[str, Any]) -> AgentRequirements | None:
        builder_state = self._load_builder_state(working_state)
        if not isinstance(builder_state.pending_requirements, dict):
            return None
        return self.normalize_requirements_payload(builder_state.pending_requirements)

    def store_pending_blueprint(
        self,
        working_state: dict[str, Any],
        blueprint: str | dict[str, Any] | AgentBlueprint,
    ) -> dict[str, Any]:
        normalized = self.draft_blueprint(blueprint)
        finalization = self.finalize_blueprint(normalized)
        builder_state = self._load_builder_state(working_state)
        builder_state.pending_blueprint = normalized.model_dump(mode="json")
        builder_state.pending_blueprint_summary = self.summarize_blueprint(normalized)
        builder_state.tool_plan = self.build_tool_plan(normalized).model_dump(mode="json")
        builder_state.finalization_status = str(finalization["status"])
        builder_state.awaiting_confirmation = (
            builder_state.finalization_status == "ready_to_generate"
        )
        builder_state.stage = (
            "awaiting_confirmation" if builder_state.awaiting_confirmation else "blueprint_drafted"
        )
        builder_state.last_build_result = {
            "status": "pending",
            "message": "已更新待确认 blueprint。",
        }
        return self._merge_builder_state(working_state, builder_state)

    def load_pending_blueprint(self, working_state: dict[str, Any]) -> AgentBlueprint | None:
        builder_state = self._load_builder_state(working_state)
        if not isinstance(builder_state.pending_blueprint, dict):
            return None
        return self.normalize_blueprint_payload(builder_state.pending_blueprint)

    def clear_pending_blueprint(
        self,
        working_state: dict[str, Any],
        build_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        builder_state = self._load_builder_state(working_state)
        builder_state.pending_blueprint = None
        builder_state.pending_blueprint_summary = ""
        builder_state.tool_plan = {}
        builder_state.finalization_status = "draft"
        builder_state.awaiting_confirmation = False
        builder_state.stage = (
            "requirements_collected"
            if builder_state.pending_requirements
            else "requirements_collection"
        )
        builder_state.last_build_result = build_result or {
            "status": "cleared",
            "message": "已清空待确认 blueprint。",
        }
        return self._merge_builder_state(working_state, builder_state)

    def clear_pending_requirements(self, working_state: dict[str, Any]) -> dict[str, Any]:
        builder_state = self._load_builder_state(working_state)
        builder_state.pending_requirements = None
        builder_state.requirements_summary = ""
        builder_state.stage = "requirements_collection"
        return self._merge_builder_state(working_state, builder_state)

    def mark_build_failure(
        self,
        working_state: dict[str, Any],
        blueprint: str | dict[str, Any] | AgentBlueprint,
        error: str,
    ) -> dict[str, Any]:
        next_state = self.store_pending_blueprint(working_state, blueprint)
        builder_state = self._load_builder_state(next_state)
        builder_state.last_build_result = {"status": "failed", "message": error}
        builder_state.stage = "blueprint_drafted"
        return self._merge_builder_state(next_state, builder_state)

    def is_confirmation_input(self, user_input: str) -> bool:
        return user_input.strip() == BUILDER_CONFIRMATION_PHRASE

    def build_completed_result(self, result: BuildResult) -> dict[str, Any]:
        return {
            "status": result.status,
            "message": result.message or "已生成 agent 脚手架。",
            "created_files": [str(path) for path in result.created_files],
            "validation_messages": result.validation_messages,
            "chat_entry": str(result.chat_entry) if result.chat_entry else None,
        }

    def create_agent_directory(self, blueprint: AgentBlueprint) -> Path:
        agent_dir = self.agents_root / blueprint.agent_id
        (agent_dir / "workspace" / "memory").mkdir(parents=True, exist_ok=True)
        (agent_dir / "skills").mkdir(parents=True, exist_ok=True)
        return agent_dir

    def write_workspace_documents(self, blueprint: AgentBlueprint) -> list[Path]:
        return self.generate_workspace(blueprint)

    def generate_workspace(self, blueprint: AgentBlueprint) -> list[Path]:
        normalized = self.draft_blueprint(blueprint)
        agent_dir = self.create_agent_directory(normalized)
        created: list[Path] = []
        for relative_path, content in render_workspace_documents(normalized).items():
            path = agent_dir / "workspace" / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            created.append(path)
        return created

    def write_skill_packages(self, blueprint: AgentBlueprint) -> list[Path]:
        return self.generate_skills(blueprint)

    def generate_skills(self, blueprint: AgentBlueprint) -> list[Path]:
        normalized = self.draft_blueprint(blueprint)
        agent_dir = self.create_agent_directory(normalized)
        created: list[Path] = []
        for skill in normalized.skills:
            path = agent_dir / "skills" / skill.name / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_skill_markdown(skill), encoding="utf-8")
            created.append(path)
        return created

    def write_local_tool_module(self, blueprint: AgentBlueprint) -> list[Path]:
        return self.generate_tools(blueprint)

    def generate_tools(self, blueprint: AgentBlueprint) -> list[Path]:
        normalized = self.draft_blueprint(blueprint)
        content = render_tools_module(normalized.tool_plan)
        if not content.strip():
            return []
        agent_dir = self.create_agent_directory(normalized)
        path = agent_dir / "tools.py"
        path.write_text(content, encoding="utf-8")
        return [path]

    def write_agent_spec(self, blueprint: AgentBlueprint) -> list[Path]:
        return self.generate_spec(blueprint)

    def generate_spec(self, blueprint: AgentBlueprint) -> list[Path]:
        normalized = self.draft_blueprint(blueprint)
        agent_dir = self.create_agent_directory(normalized)
        spec_path = agent_dir / "spec.py"
        init_path = agent_dir / "__init__.py"
        spec_path.write_text(render_agent_spec(normalized), encoding="utf-8")
        init_path.write_text(render_agent_init(normalized), encoding="utf-8")
        return [spec_path, init_path]

    def update_agents_exports(self, blueprint: AgentBlueprint) -> Path:
        exports_path = self.agents_root / "__init__.py"
        factory_name = f"create_{blueprint.agent_id}_agent"
        import_line = f"from .{blueprint.agent_id} import {factory_name}"
        if exports_path.exists():
            content = exports_path.read_text(encoding="utf-8")
        else:
            exports_path.parent.mkdir(parents=True, exist_ok=True)
            content = ""

        imports = [line for line in content.splitlines() if line.startswith("from .")]
        others = [
            line
            for line in content.splitlines()
            if not line.startswith("from .") and not line.startswith("__all__")
        ]
        if import_line not in imports:
            imports.append(import_line)
        imports = sorted(dict.fromkeys(imports))

        exported = re.findall(r'"([^"]+)"', content)
        if factory_name not in exported:
            exported.append(factory_name)
        exported = sorted(dict.fromkeys(exported))

        blocks: list[str] = []
        if imports:
            blocks.append("\n".join(imports))
        if others:
            blocks.append("\n".join(line for line in others if line.strip()))
        blocks.append(f"__all__ = {exported!r}")
        exports_path.write_text("\n\n".join(blocks).strip() + "\n", encoding="utf-8")
        return exports_path

    def create_chat_entry_script(self, blueprint: AgentBlueprint) -> Path | None:
        normalized = self.draft_blueprint(blueprint)
        if not normalized.create_chat_entry:
            return None
        path = self.project_root / f"chat_with_{normalized.agent_id}_agent.py"
        path.write_text(render_chat_entry(normalized), encoding="utf-8")
        return path

    def validate_generated_agent(self, agent_id: str) -> list[str]:
        errors: list[str] = []
        agent_dir = self.agents_root / agent_id

        # 1. Check workspace files exist
        workspace_dir = agent_dir / "workspace"
        required_workspace_files = ["AGENTS.md", "SOUL.md", "TOOLS.md", "USER.md"]
        for filename in required_workspace_files:
            filepath = workspace_dir / filename
            if not filepath.exists():
                errors.append(f"缺少工作区文件: {filepath}")

        # 2. Check spec.py exists and is importable
        spec_path = agent_dir / "spec.py"
        if not spec_path.exists():
            errors.append(f"未找到 spec.py: {spec_path}")
            return errors

        factory_name = f"create_{agent_id}_agent"
        sys.path.insert(0, str(agent_dir))
        try:
            spec = importlib.util.spec_from_file_location(f"{agent_id}_spec", spec_path)
            if spec is None or spec.loader is None:
                errors.append("无法创建模块加载器。")
                return errors
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, factory_name):
                errors.append(f"未找到工厂函数：{factory_name}")
        except Exception as exc:
            errors.append(f"导入校验失败：{exc}")
        finally:
            if sys.path and sys.path[0] == str(agent_dir):
                sys.path.pop(0)

        # 3. Check __init__.py exists and exports the factory
        init_path = agent_dir / "__init__.py"
        if init_path.exists():
            init_content = init_path.read_text(encoding="utf-8")
            if factory_name not in init_content:
                errors.append(f"__init__.py 未导出工厂函数: {factory_name}")
        else:
            errors.append(f"缺少 __init__.py: {init_path}")

        # 4. Check skills directory if it exists
        skills_dir = agent_dir / "skills"
        if skills_dir.exists():
            skill_md_files = list(skills_dir.rglob("SKILL.md"))
            if not skill_md_files:
                errors.append(f"技能目录为空: {skills_dir}")
        else:
            errors.append(f"缺少技能目录: {skills_dir}")

        # 5. Check tools.py if it exists
        tools_path = agent_dir / "tools.py"
        if tools_path.exists():
            tools_spec = importlib.util.spec_from_file_location(f"{agent_id}_tools", tools_path)
            if tools_spec is not None and tools_spec.loader is not None:
                try:
                    tools_module = importlib.util.module_from_spec(tools_spec)
                    tools_spec.loader.exec_module(tools_module)
                except Exception as exc:
                    errors.append(f"工具模块导入失败: {exc}")

        return errors if errors else ["校验通过。"]

    def _rollback_generated_files(self, created_files: list[Path], agent_dir: Path) -> None:
        """删除已生成的文件和目录，回滚部分生成的结果。"""
        import shutil

        # 删除所有已创建的文件（逆序）
        for filepath in reversed(created_files):
            if filepath.exists():
                if filepath.is_file():
                    filepath.unlink(missing_ok=True)

        # 如果 agent 目录存在且为空，删除它
        if agent_dir.exists() and not any(agent_dir.iterdir()):
            shutil.rmtree(agent_dir, ignore_errors=True)

    def generate_agent_scaffold(self, blueprint: AgentBlueprint) -> BuildResult:
        normalized = self.draft_blueprint(blueprint)
        issues = self.validate_blueprint(normalized)
        if issues:
            raise ValueError("; ".join(issues))

        agent_dir = self.agents_root / normalized.agent_id
        created_files: list[Path] = []

        try:
            created_files.extend(self.generate_workspace(normalized))
            created_files.extend(self.generate_skills(normalized))
            created_files.extend(self.generate_tools(normalized))
            created_files.extend(self.generate_spec(normalized))
            created_files.append(self.update_agents_exports(normalized))
            chat_entry = self.create_chat_entry_script(normalized)
            if chat_entry is not None:
                created_files.append(chat_entry)
            validation_messages = self.validate_generated_agent(normalized.agent_id)
            return BuildResult(
                agent_id=normalized.agent_id,
                agent_dir=agent_dir,
                created_files=created_files,
                validation_messages=validation_messages,
                chat_entry=chat_entry,
                factory_name=f"create_{normalized.agent_id}_agent",
                status="completed",
                message="已生成 agent 脚手架。",
            )
        except Exception as exc:
            self._rollback_generated_files(created_files, agent_dir)
            return BuildResult(
                agent_id=normalized.agent_id,
                agent_dir=agent_dir,
                created_files=[],
                validation_messages=[f"生成失败，已回滚: {exc}"],
                chat_entry=None,
                factory_name=f"create_{normalized.agent_id}_agent",
                status="failed",
                message=f"生成失败: {exc}",
            )

    def generate_from_blueprint(self, blueprint: AgentBlueprint) -> BuildResult:
        return self.generate_agent_scaffold(blueprint)
