"""从 workspace 装载 bootstrap 文档。"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from agent_framework.bootstrap.models import BootstrapDocument, BootstrapSnapshot, InjectionPolicy
from agent_framework.config.settings import FrameworkSettings


class BootstrapLoader:
    """扫描标准 workspace 文档，并产出可注入的 snapshot。"""

    def __init__(self, settings: FrameworkSettings):
        self.settings = settings
        self.policy = InjectionPolicy()

    def load_workspace(self, workspace_dir: str | Path) -> BootstrapSnapshot:
        # 文档名约定集中定义在这里，保证 workspace 契约稳定且可审计。
        base = Path(workspace_dir)
        candidates = {
            "AGENTS.md": ("system", False),
            "SOUL.md": ("system", False),
            "USER.md": ("context", True),
            "TOOLS.md": ("context", True),
            "IDENTITY.md": ("system", True),
            "BOOTSTRAP.md": ("retrieval", True),
            "HEARTBEAT.md": ("hook", True),
            "memory/MEMORY.md": ("retrieval", True),
        }

        documents: Dict[str, BootstrapDocument] = {}
        for relative_name, (inject_mode, optional) in candidates.items():
            path = base / relative_name
            content = ""
            if path.exists():
                content = path.read_text(encoding="utf-8")
            documents[relative_name] = BootstrapDocument(
                name=relative_name,
                path=path,
                content=content,
                inject_mode=inject_mode,
                optional=optional,
            )

        return BootstrapSnapshot(
            workspace_dir=base,
            documents=documents,
            policy=self.policy,
            max_chars_per_file=self.settings.max_bootstrap_chars_per_file,
            max_chars_total=self.settings.max_bootstrap_chars_total,
        )
