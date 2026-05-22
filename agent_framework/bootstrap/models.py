"""bootstrap 文档模型。

这一层负责定义 workspace 文档在运行时里的表示方式，以及注入预算控制逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(slots=True)
class BootstrapDocument:
    """单个 bootstrap 文档的运行时表示。"""

    name: str
    path: Path
    content: str
    inject_mode: str
    optional: bool = False

    @property
    def exists(self) -> bool:
        return self.path.exists()


@dataclass(slots=True)
class InjectionPolicy:
    """定义不同 bootstrap 文档的默认注入分组。"""

    system_docs: List[str] = field(default_factory=lambda: ["AGENTS.md", "SOUL.md", "IDENTITY.md"])
    context_docs: List[str] = field(default_factory=lambda: ["USER.md", "TOOLS.md"])
    retrievable_docs: List[str] = field(default_factory=lambda: ["BOOTSTRAP.md", "memory/MEMORY.md"])


@dataclass(slots=True)
class BootstrapSection:
    """最终进入 prompt 的标准 section 结构。"""

    title: str
    content: str
    source: str
    mode: str


@dataclass(slots=True)
class BootstrapSnapshot:
    """某个 workspace 在当前运行时的文档快照。

    snapshot 既保留原始文档内容，也内置注入预算，避免上层每次都重复关心
    截断和优先级细节。
    """

    workspace_dir: Path
    documents: Dict[str, BootstrapDocument]
    policy: InjectionPolicy
    max_chars_per_file: int
    max_chars_total: int

    def get(self, name: str) -> Optional[BootstrapDocument]:
        return self.documents.get(name)

    def _trim(self, text: str, budget: int) -> str:
        if len(text) <= budget:
            return text
        head = text[: max(0, budget - 64)].rstrip()
        return f"{head}\n\n[truncated to {budget} chars]"

    def build_sections(self, mode: str) -> List[BootstrapSection]:
        # 主 agent 和 sub-agent 的注入集合不同，避免子代理默认拿到完整主会话背景。
        if mode == "main":
            ordered_names = self.policy.system_docs + self.policy.context_docs
        elif mode == "subagent":
            ordered_names = ["AGENTS.md", "SOUL.md", "IDENTITY.md"]
        else:
            ordered_names = self.policy.retrievable_docs

        remaining = self.max_chars_total
        sections: List[BootstrapSection] = []
        for name in ordered_names:
            document = self.get(name)
            if document is None or not document.content.strip():
                continue
            if remaining <= 0:
                break
            budget = min(self.max_chars_per_file, remaining)
            content = self._trim(document.content.strip(), budget)
            sections.append(
                BootstrapSection(
                    title=name,
                    content=content,
                    source=str(document.path),
                    mode=document.inject_mode,
                )
            )
            remaining -= len(content)
        return sections
