from __future__ import annotations

from pathlib import Path
from typing import List

from ruamel.yaml import YAML

from agent_framework.plugins.models import PluginManifest


class PluginLoader:
    def __init__(self) -> None:
        self.yaml = YAML(typ="safe")

    def scan(self, root_dir: str | Path) -> List[PluginManifest]:
        manifests: List[PluginManifest] = []
        base = Path(root_dir)
        if not base.exists():
            return manifests

        for path in base.rglob("plugin.yaml"):
            content = self.yaml.load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(content, dict):
                continue
            manifest = PluginManifest(**content, root_dir=path.parent)
            manifests.append(manifest)
        return manifests
