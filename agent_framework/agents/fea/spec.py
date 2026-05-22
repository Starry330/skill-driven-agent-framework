"""FEA agent 的正式注册入口。"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import List, Tuple

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from agent_framework.config.settings import FrameworkSettings, get_settings
from agent_framework.core.agent import AgentSpec
from agent_framework.tools.adapters.local import build_local_tool_spec
from agent_framework.tools.models import ToolSpec
from agent_framework.tools.policy import ToolPolicy
from agent_framework.tools.basic import calculator, current_time
from agent_framework.tools.file_tools import list_directory, read_local_file
from agent_framework.agents.fea.stp_analyzer import STPAnalyzerCN
from agent_framework.agents.fea.stp_viewer import STPViewer


def create_fea_agent(
    llm: BaseChatModel,
    settings: FrameworkSettings | None = None,
) -> Tuple[AgentSpec, List[ToolSpec]]:
    """构造静力学 FEA agent 的规格与工具集合。"""

    _ = settings or get_settings()

    @tool
    def analyze_stp_file(file_path: str) -> str:
        """Analyze an STP/STEP file and return a geometry report."""

        # STPAnalyzerCN 以 stdout 形式输出分析报告，这里做一次捕获并转成普通文本返回。
        previous_stdout = sys.stdout
        buffer = io.StringIO()
        sys.stdout = buffer
        try:
            analyzer = STPAnalyzerCN(file_path)
            analyzer.run()
            return buffer.getvalue()
        finally:
            sys.stdout = previous_stdout

    @tool
    def get_multiview(file_path: str) -> str:
        """Generate a multiview image for an STP/STEP file and return its path."""

        if not os.path.exists(file_path):
            raise RuntimeError(f"file not found: {file_path}")
        viewer = STPViewer(file_path)
        viewer.extract_features()
        output_path = viewer.generate_multiview(output_dir=".")
        return os.path.abspath(output_path)

    workspace_dir = Path(__file__).resolve().parent / "workspace"
    skills_dir = Path(__file__).resolve().parent / "skills"
    # FEA skill 允许的工具集合比 research 更窄，重点是几何分析和文件读取。
    spec = AgentSpec(
        agent_id="fea",
        name="Static Structural FEA Assistant",
        workspace_dir=workspace_dir,
        skills_dirs=[skills_dir],
        llm=llm,
        tool_policy=ToolPolicy(
            allowlist=[
                "calculator",
                "current_time",
                "read_local_file",
                "list_directory",
                "analyze_stp_file",
                "get_multiview",
            ],
            skill_tool_overrides={
                "static-structural-fea": [
                    "analyze_stp_file",
                    "get_multiview",
                    "read_local_file",
                    "list_directory",
                    "calculator",
                    "current_time",
                ]
            },
        ),
        memory_namespaces=["semantic", "episodic", "task_memory", "tool_notes", "procedures", "episodes", "user_preferences"],
        workflow_name="fea_agent",
    )
    tools = [
        build_local_tool_spec(calculator),
        build_local_tool_spec(current_time),
        build_local_tool_spec(read_local_file),
        build_local_tool_spec(list_directory),
        build_local_tool_spec(analyze_stp_file, timeout_seconds=60),
        build_local_tool_spec(get_multiview, timeout_seconds=60),
    ]
    return spec, tools
