"""定义 agent 的静态规格与单次运行上下文。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from langchain_core.language_models import BaseChatModel

from agent_framework.tools.policy import ToolPolicy


@dataclass(slots=True)
class AgentSpec:
    """描述一个 agent 在框架中的长期配置。

    这个对象是 Gateway 注册 agent 的最小单元，包含 workspace、skills、
    LLM、tool policy 和 memory namespace 等跨会话稳定配置。
    """

    agent_id: str
    name: str
    workspace_dir: Path
    skills_dirs: List[Path]
    llm: BaseChatModel
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)
    memory_namespaces: List[str] = field(default_factory=lambda: ["semantic", "episodic", "user_memory", "task_memory", "procedures", "episodes", "user_preferences"])
    workflow_name: str = "default"
    max_active_skills: int = 2
    requires_active_skill: bool = True
