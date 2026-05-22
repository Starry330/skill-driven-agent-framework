from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from langchain_core.language_models import BaseChatModel

from agent_framework.config.settings import FrameworkSettings, get_settings
from agent_framework.core.agent import AgentSpec
from agent_framework.tools.adapters.local import build_local_tool_spec
from agent_framework.tools.models import ToolSpec
from agent_framework.tools.policy import ToolPolicy


def create_technical_interview_assistant_agent(
    llm: BaseChatModel,
    settings: FrameworkSettings | None = None,
) -> Tuple[AgentSpec, List[ToolSpec]]:
    cfg = settings or get_settings()
    workspace_dir = Path(__file__).resolve().parent / "workspace"
    skills_dir = Path(__file__).resolve().parent / "skills"

    spec = AgentSpec(
        agent_id="technical_interview_assistant",
        name="技术面试助手",
        workspace_dir=workspace_dir,
        skills_dirs=[skills_dir],
        llm=llm,
        tool_policy=ToolPolicy(
            allowlist=[
            ],
            skill_tool_overrides={
            },
        ),
        memory_namespaces=["interview_history", "user_skill_profile", "question_bank"],
        workflow_name="technical-interview-workflow",
        requires_active_skill=True,
    )

    tools: List[ToolSpec] = [
    ]
    return spec, tools
