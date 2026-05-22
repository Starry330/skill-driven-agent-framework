from __future__ import annotations

import os
from pathlib import Path


def load_project_env(project_root: Path | None = None) -> dict[str, str]:
    root = project_root or Path(__file__).resolve().parents[2]
    values = _read_env_file(root / ".env")
    values.update(os.environ)
    return values


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = _clean_env_value(raw_value.strip())
    return values


def _clean_env_value(value: str) -> str:
    if not value:
        return ""

    quote = value[0]
    if quote in {"'", '"'}:
        end_index = value.find(quote, 1)
        if end_index != -1:
            return value[1:end_index]
        return value[1:]

    comment_index = value.find(" #")
    if comment_index != -1:
        value = value[:comment_index]
    return value.strip()
