"""SKILL.md 加载器。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ruamel.yaml import YAML

from agent_framework.skills.models import SkillSpec


class SkillLoader:
    """负责把 markdown frontmatter 解析成 SkillSpec。"""

    def __init__(self) -> None:
        self.yaml = YAML(typ="safe")

    def load(self, path: str | Path) -> SkillSpec:
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_frontmatter(content)
        if "name" not in frontmatter:
            raise ValueError(f"Skill file {file_path} missing required field 'name'")

        spec = SkillSpec(
            name=str(frontmatter["name"]),
            description=str(frontmatter.get("description", "")),
            body=body.strip(),
            path=file_path,
            triggers=[str(item) for item in frontmatter.get("triggers", [])],
            slash_command=str(frontmatter.get("slash_command", "")),
            required_tools=[str(item) for item in frontmatter.get("required_tools", [])],
            permissions=[str(item) for item in frontmatter.get("permissions", [])],
            input_schema=dict(frontmatter.get("input_schema", {})),
            output_schema=dict(frontmatter.get("output_schema", {})),
            decision_logic=self._normalize_mapping_list(frontmatter.get("decision_logic", [])),
            constraints=[str(item) for item in frontmatter.get("constraints", [])],
            failure_modes=self._normalize_mapping_list(frontmatter.get("failure_modes", [])),
            fallback_strategy=self._normalize_mapping_list(frontmatter.get("fallback_strategy", [])),
            tool_policy=dict(frontmatter.get("tool_policy", {})),
            dependencies=[str(item) for item in frontmatter.get("dependencies", [])],
            availability_checks=[str(item) for item in frontmatter.get("availability_checks", [])],
            subagent_allowed=bool(frontmatter.get("subagent_allowed", False)),
            enabled=bool(frontmatter.get("enabled", True)),
            metadata=dict(frontmatter.get("metadata", {})),
        )
        self._validate_protocol(spec)
        return spec

    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        # frontmatter 缺失时允许降级为空元数据，便于逐步迁移旧 skill 文档。
        pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
        match = pattern.match(content)
        if not match:
            return {}, content
        metadata = self.yaml.load(match.group(1)) or {}
        if not isinstance(metadata, dict):
            raise ValueError("Skill frontmatter must be a mapping")
        return metadata, match.group(2)

    def _normalize_mapping_list(self, payload: Any) -> List[Dict[str, object]]:
        if payload is None:
            return []
        if not isinstance(payload, list):
            raise ValueError("Protocol list fields must be arrays")
        normalized: List[Dict[str, object]] = []
        for item in payload:
            if isinstance(item, dict):
                normalized.append({str(key): value for key, value in item.items()})
            elif isinstance(item, str):
                normalized.append({"rule": item})
            else:
                raise ValueError("Protocol list entries must be mappings or strings")
        return normalized

    def _validate_protocol(self, spec: SkillSpec) -> None:
        if not self._is_builder_skill(spec):
            return
        required_sections = {
            "input_schema": spec.input_schema,
            "output_schema": spec.output_schema,
            "decision_logic": spec.decision_logic,
            "constraints": spec.constraints,
            "failure_modes": spec.failure_modes,
            "fallback_strategy": spec.fallback_strategy,
            "tool_policy": spec.tool_policy,
        }
        missing = [name for name, value in required_sections.items() if not value]
        if missing:
            raise ValueError(
                f"Builder skill '{spec.name}' missing required protocol fields: {', '.join(missing)}"
            )
        if not isinstance(spec.input_schema, dict) or "type" not in spec.input_schema:
            raise ValueError(f"Builder skill '{spec.name}' must define a structured input_schema")
        if not isinstance(spec.output_schema, dict) or "type" not in spec.output_schema:
            raise ValueError(f"Builder skill '{spec.name}' must define a structured output_schema")

    def _is_builder_skill(self, spec: SkillSpec) -> bool:
        category = str(spec.metadata.get("category", ""))
        if category == "builder":
            return True
        return "agents/builder/skills" in spec.path.as_posix()
