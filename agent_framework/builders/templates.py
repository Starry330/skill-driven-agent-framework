"""Builder 生成脚手架时使用的代码与文档模板。"""

from __future__ import annotations

from io import StringIO
from textwrap import dedent
from typing import Dict, Iterable, Tuple

from ruamel.yaml import YAML

from agent_framework.builders.models import AgentBlueprint, SkillBlueprint, ToolBlueprint

_YAML = YAML()
_YAML.default_flow_style = False


BUILTIN_TOOL_IMPORTS: Dict[str, Tuple[str, str]] = {
    "calculator": ("agent_framework.tools.basic", "calculator"),
    "current_time": ("agent_framework.tools.basic", "current_time"),
    "read_local_file": ("agent_framework.tools.file_tools", "read_local_file"),
    "list_directory": ("agent_framework.tools.file_tools", "list_directory"),
}


def _dump_frontmatter(data: Dict[str, object]) -> str:
    buffer = StringIO()
    _YAML.dump(data, buffer)
    return buffer.getvalue().strip()


def render_skill_markdown(skill: SkillBlueprint) -> str:
    frontmatter = _dump_frontmatter(
        {
            "name": skill.name,
            "description": skill.description,
            "triggers": skill.triggers,
            "required_tools": skill.required_tools,
            "permissions": skill.permissions,
            "input_schema": skill.input_schema,
            "output_schema": skill.output_schema,
            "decision_logic": skill.decision_logic,
            "constraints": skill.constraints,
            "failure_modes": skill.failure_modes,
            "fallback_strategy": skill.fallback_strategy,
            "tool_policy": skill.tool_policy,
            "subagent_allowed": skill.subagent_allowed,
            "dependencies": skill.dependencies,
            "availability_checks": skill.availability_checks,
            "enabled": skill.enabled,
            "metadata": skill.metadata,
        }
    )
    return f"---\n{frontmatter}\n---\n{skill.body.strip()}\n"


def render_workspace_documents(blueprint: AgentBlueprint) -> Dict[str, str]:
    style_text = "\n".join(f"- {item}" for item in blueprint.style_constraints) or "- 保持清晰、务实、可执行。"
    tool_lines = "\n".join(f"- {tool.name}" for tool in blueprint.tool_plan) or "- 当前未声明工具。"
    return {
        "AGENTS.md": blueprint.workspace_docs.agents_md.strip()
        or dedent(
            f"""
            # Agent Rules

            - 你是 `{blueprint.name}`。
            - 你的核心目标：{blueprint.goal}
            - 优先给出正确、清晰、可执行的回答。
            - 不要虚构工具能力；工具不足时必须明确说明限制。
            """
        ).strip(),
        "SOUL.md": blueprint.workspace_docs.soul_md.strip()
        or dedent(
            f"""
            # Role

            {blueprint.role}

            # Goal

            {blueprint.goal}

            # Style Constraints

            {style_text}
            """
        ).strip(),
        "TOOLS.md": blueprint.workspace_docs.tools_md.strip()
        or dedent(
            f"""
            # Tools

            以下工具会被注册到当前 agent：

            {tool_lines}
            """
        ).strip(),
        "USER.md": blueprint.workspace_docs.user_md.strip() or "# User\n\n- 默认用户画像待补充。",
        "memory/MEMORY.md": blueprint.workspace_docs.memory_md.strip()
        or "# Memory\n\n- 记录长期偏好、任务历史和可复用经验。",
    }


def render_tools_module(tools: Iterable[ToolBlueprint]) -> str:
    custom_tools = [tool for tool in tools if not tool.reuse_existing and tool.implementation_code.strip()]
    if not custom_tools:
        return ""

    blocks = [
        '"""Builder 为当前 agent 生成的本地工具。"""',
        "",
        "from __future__ import annotations",
        "",
        "from langchain_core.tools import tool",
        "",
    ]
    for tool in custom_tools:
        blocks.append(tool.implementation_code.strip())
        blocks.append("")
    return "\n".join(blocks).rstrip() + "\n"


def render_agent_init(blueprint: AgentBlueprint) -> str:
    factory_name = f"create_{blueprint.agent_id}_agent"
    return f"from .spec import {factory_name}\n\n__all__ = [\"{factory_name}\"]\n"


def render_agent_spec(blueprint: AgentBlueprint) -> str:
    factory_name = f"create_{blueprint.agent_id}_agent"
    builtin_reused = [tool for tool in blueprint.tool_plan if tool.reuse_existing and tool.existing_tool_name]
    custom_tools = [tool for tool in blueprint.tool_plan if not tool.reuse_existing and tool.implementation_code.strip()]

    lines = [
        "from __future__ import annotations",
        "",
        "from pathlib import Path",
        "from typing import List, Tuple",
        "",
        "from langchain_core.language_models import BaseChatModel",
        "",
        "from agent_framework.config.settings import FrameworkSettings, get_settings",
        "from agent_framework.core.agent import AgentSpec",
        "from agent_framework.tools.adapters.local import build_local_tool_spec",
        "from agent_framework.tools.models import ToolSpec",
        "from agent_framework.tools.policy import ToolPolicy",
    ]

    seen_imports: set[tuple[str, str]] = set()
    for tool in builtin_reused:
        assert tool.existing_tool_name is not None
        module_name, symbol = BUILTIN_TOOL_IMPORTS[tool.existing_tool_name]
        key = (module_name, symbol)
        if key not in seen_imports:
            lines.append(f"from {module_name} import {symbol}")
            seen_imports.add(key)

    if custom_tools:
        lines.extend(
            [
                "try:",
                f"    from .tools import {', '.join(tool.name for tool in custom_tools)}",
                "except ImportError:",
                "    import importlib.util",
                "    _TOOLS_PATH = Path(__file__).resolve().parent / 'tools.py'",
                "    _TOOLS_SPEC = importlib.util.spec_from_file_location(f'{__name__}_local_tools', _TOOLS_PATH)",
                "    if _TOOLS_SPEC is None or _TOOLS_SPEC.loader is None:",
                "        raise ImportError(f'无法加载本地 tools.py: {_TOOLS_PATH}')",
                "    _TOOLS_MODULE = importlib.util.module_from_spec(_TOOLS_SPEC)",
                "    _TOOLS_SPEC.loader.exec_module(_TOOLS_MODULE)",
            ]
        )
        for tool in custom_tools:
            lines.append(f"    {tool.name} = getattr(_TOOLS_MODULE, '{tool.name}')")

    lines.extend(["", ""])
    lines.append(f"def {factory_name}(")
    lines.append("    llm: BaseChatModel,")
    lines.append("    settings: FrameworkSettings | None = None,")
    lines.append(") -> Tuple[AgentSpec, List[ToolSpec]]:")
    lines.append("    cfg = settings or get_settings()")
    lines.append("    workspace_dir = Path(__file__).resolve().parent / \"workspace\"")
    lines.append("    skills_dir = Path(__file__).resolve().parent / \"skills\"")
    lines.append("")
    lines.append("    spec = AgentSpec(")
    lines.append(f"        agent_id=\"{blueprint.agent_id}\",")
    lines.append(f"        name=\"{blueprint.name}\",")
    lines.append("        workspace_dir=workspace_dir,")
    lines.append("        skills_dirs=[skills_dir],")
    lines.append("        llm=llm,")
    lines.append("        tool_policy=ToolPolicy(")
    lines.append("            allowlist=[")
    for tool in blueprint.tool_plan:
        allow_name = tool.existing_tool_name or tool.name
        lines.append(f"                \"{allow_name}\",")
    lines.append("            ],")
    lines.append("            skill_tool_overrides={")
    for skill_name, names in blueprint.tool_policy.skill_tool_overrides.items():
        override_names = ", ".join(f'\"{name}\"' for name in names)
        lines.append(f"                \"{skill_name}\": [{override_names}],")
    lines.append("            },")
    lines.append("        ),")
    namespaces = ", ".join(f'\"{item}\"' for item in blueprint.memory_namespaces)
    lines.append(f"        memory_namespaces=[{namespaces}],")
    lines.append(f"        workflow_name=\"{blueprint.workflow_name}\",")
    lines.append("        requires_active_skill=True,")
    lines.append("    )")
    lines.append("")
    lines.append("    tools: List[ToolSpec] = [")
    for tool in builtin_reused:
        lines.append(f"        build_local_tool_spec({tool.existing_tool_name}),")
    for tool in custom_tools:
        extra: list[str] = []
        if tool.side_effect_level != "low":
            extra.append(f'side_effect_level=\"{tool.side_effect_level}\"')
        if tool.timeout_seconds != 30:
            extra.append(f"timeout_seconds={tool.timeout_seconds}")
        suffix = ", " + ", ".join(extra) if extra else ""
        lines.append(f"        build_local_tool_spec({tool.name}{suffix}),")
    lines.append("    ]")
    lines.append("    return spec, tools")
    lines.append("")
    return "\n".join(lines)


def render_chat_entry(blueprint: AgentBlueprint) -> str:
    factory_name = f"create_{blueprint.agent_id}_agent"
    template = f"""\
from __future__ import annotations

import uuid
from pathlib import Path

from langchain_openai import ChatOpenAI

from agent_framework.agents import {factory_name}
from agent_framework.config.settings import FrameworkSettings
from agent_framework.core import Gateway


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def main() -> None:
    root = Path(__file__).resolve().parent
    settings = FrameworkSettings(
        workspace_root=root,
        storage_root=root / ".runtime",
        database_path=root / ".runtime" / "runtime.db",
    )
    gateway = Gateway(settings)
    spec, tools = {factory_name}(build_llm(), settings)
    gateway.register_agent(spec, tools)

    session_id = str(uuid.uuid4())
    print(f"=== Connected to {{spec.name}} ===")
    print(f"Session: {{session_id}}")
    print("输入 exit 退出。")

    while True:
        user_input = input("\\nYou: ").strip()
        if user_input.lower() in {{"exit", "quit"}}:
            break
        response = gateway.run(
            agent_id=spec.agent_id,
            user_input=user_input,
            session_id=session_id,
        )
        print(f"\\n{{spec.name}}:\\n{{response}}")


if __name__ == "__main__":
    main()
"""
    return template
