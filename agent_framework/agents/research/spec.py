"""Research agent 的正式注册入口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from agent_framework.config.settings import FrameworkSettings, get_settings
from agent_framework.core.agent import AgentSpec
from agent_framework.tools.adapters.local import build_local_tool_spec
from agent_framework.tools.models import ToolSpec
from agent_framework.tools.policy import ToolPolicy
from agent_framework.tools.basic import calculator, current_time
from agent_framework.tools.file_tools import list_directory, read_local_file


def create_research_agent(
    llm: BaseChatModel,
    settings: FrameworkSettings | None = None,
) -> Tuple[AgentSpec, List[ToolSpec]]:
    """构造 research agent 的规格与工具集合。"""

    cfg = settings or get_settings()

    @tool
    def web_search(query: str) -> str:
        """Search configured HTTP endpoint for the given query."""

        if not cfg.web_search_url:
            raise RuntimeError("web search provider is not configured")

        # web_search 故意设计成可配置工具：未配置 provider 时，skill runtime 会把它视为不可用能力。
        url = f"{cfg.web_search_url}?{urlencode({cfg.web_search_query_param: query})}"
        request = Request(url, headers=cfg.web_search_headers)
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310
                body = response.read().decode("utf-8", errors="ignore")
        except URLError as exc:
            raise RuntimeError(f"web search request failed: {exc}") from exc

        try:
            parsed = json.loads(body)
            return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            return body

    workspace_dir = Path(__file__).resolve().parent / "workspace"
    skills_dir = Path(__file__).resolve().parent / "skills"
    # skill_tool_overrides 把 web_search skill 的工具面收窄到最小集合，避免搜索意图误触其他工具。
    spec = AgentSpec(
        agent_id="research",
        name="Research Assistant",
        workspace_dir=workspace_dir,
        skills_dirs=[skills_dir],
        llm=llm,
        tool_policy=ToolPolicy(
            allowlist=["calculator", "current_time", "read_local_file", "list_directory", "web_search"],
            skill_tool_overrides={"web-search": ["web_search"]},
        ),
        memory_namespaces=["semantic", "episodic", "user_memory", "task_memory", "tool_notes", "procedures", "episodes", "user_preferences"],
        workflow_name="research_agent",
    )
    tools = [
        build_local_tool_spec(calculator),
        build_local_tool_spec(current_time),
        build_local_tool_spec(read_local_file),
        build_local_tool_spec(list_directory),
        build_local_tool_spec(web_search, side_effect_level="medium", workspace_scope="external", timeout_seconds=15),
    ]
    return spec, tools
