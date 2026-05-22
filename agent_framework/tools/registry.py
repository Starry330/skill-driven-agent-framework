"""工具注册表。

本地工具和未来的 MCP 工具都会在这一层收敛成统一的 ToolSpec。
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.tools import BaseTool

from agent_framework.tools.adapters.local import build_local_tool_spec
from agent_framework.tools.models import ToolSpec


class ToolRegistry:
    """按名称持有当前可执行工具。"""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def all(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def names(self) -> Iterable[str]:
        return self._tools.keys()

    def get_base_tool(self, name: str) -> BaseTool:
        return self._tools[name].base_tool

    def execute_tool(self, name: str, payload: Any) -> Any:
        """已弃用：请使用 ToolExecutor.execute() 以确保策略/审批/审计链路完整。"""
        warnings.warn(
            "ToolRegistry.execute_tool() 已弃用，请使用 ToolExecutor.execute() "
            "以确保策略/审批/审计链路完整。",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_base_tool(name).invoke(payload)


class LocalToolRegistry(ToolRegistry):
    """兼容旧式 BaseTool 注册方式的薄包装。"""

    def register_tool(self, tool: BaseTool) -> None:
        self.register(build_local_tool_spec(tool))
