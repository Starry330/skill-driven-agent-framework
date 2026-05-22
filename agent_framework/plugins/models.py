from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    name: str
    version: str
    entrypoint: str
    enabled: bool = True
    provides: List[str] = Field(default_factory=list)
    config_schema: Dict[str, object] = Field(default_factory=dict)
    compat: Dict[str, object] = Field(default_factory=dict)
    root_dir: Path | None = None
