from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field

from .env import load_project_env

DEFAULT_MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
DEFAULT_MIMO_MODEL = "mimo-v2.5"


class LlmSettings(BaseModel):
    base_url: str = DEFAULT_MIMO_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_MIMO_MODEL
    streaming: bool = True
    temperature: float = 0.2
    max_completion_tokens: int = 8192


class FrameworkSettings(BaseModel):
    workspace_root: Path = Field(default_factory=lambda: Path.cwd())
    storage_root: Path = Field(default_factory=lambda: Path("storage"))
    database_path: Path = Field(default_factory=lambda: Path("storage/runtime.db"))
    debug: bool = False
    max_bootstrap_chars_per_file: int = 4_000
    max_bootstrap_chars_total: int = 10_000
    max_history_messages: int = 12
    summary_keep_last_messages: int = 4
    max_tool_iterations: int = 15
    memory_flush_enabled: bool = True
    memory_reflection_enabled: bool = True
    memory_reflection_interval: int = 3
    memory_confidence_threshold: float = 0.3
    memory_max_experiences_per_query: int = 5
    memory_dedup_similarity_threshold: float = 0.7
    memory_decay_half_life_days: int = 30
    web_search_url: Optional[str] = None
    web_search_query_param: str = "q"
    web_search_headers: Dict[str, str] = Field(default_factory=dict)
    builder_llm: LlmSettings = Field(default_factory=LlmSettings)
    research_llm: LlmSettings = Field(default_factory=LlmSettings)
    fea_llm: LlmSettings = Field(default_factory=LlmSettings)

    def ensure_storage_dirs(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> FrameworkSettings:
    env = load_project_env()
    settings = FrameworkSettings(
        storage_root=Path(env.get("AGENT_FRAMEWORK_STORAGE_ROOT", "storage")),
        database_path=Path(env.get("AGENT_FRAMEWORK_DATABASE_PATH", "storage/runtime.db")),
        debug=_env_bool(env, "AGENT_FRAMEWORK_DEBUG", False),
        max_bootstrap_chars_per_file=_env_int(
            env, "AGENT_FRAMEWORK_MAX_BOOTSTRAP_CHARS_PER_FILE", 4_000
        ),
        max_bootstrap_chars_total=_env_int(env, "AGENT_FRAMEWORK_MAX_BOOTSTRAP_CHARS_TOTAL", 10_000),
        max_history_messages=_env_int(env, "AGENT_FRAMEWORK_MAX_HISTORY_MESSAGES", 12),
        summary_keep_last_messages=_env_int(env, "AGENT_FRAMEWORK_SUMMARY_KEEP_LAST_MESSAGES", 4),
        max_tool_iterations=_env_int(env, "AGENT_FRAMEWORK_MAX_TOOL_ITERATIONS", 15),
        memory_flush_enabled=_env_bool(env, "AGENT_FRAMEWORK_MEMORY_FLUSH_ENABLED", True),
        memory_reflection_enabled=_env_bool(env, "AGENT_FRAMEWORK_MEMORY_REFLECTION_ENABLED", True),
        memory_reflection_interval=_env_int(env, "AGENT_FRAMEWORK_MEMORY_REFLECTION_INTERVAL", 3),
        memory_confidence_threshold=_env_float(env, "AGENT_FRAMEWORK_MEMORY_CONFIDENCE_THRESHOLD", 0.3),
        memory_max_experiences_per_query=_env_int(env, "AGENT_FRAMEWORK_MEMORY_MAX_EXPERIENCES_PER_QUERY", 5),
        memory_dedup_similarity_threshold=_env_float(env, "AGENT_FRAMEWORK_MEMORY_DEDUP_SIMILARITY_THRESHOLD", 0.7),
        memory_decay_half_life_days=_env_int(env, "AGENT_FRAMEWORK_MEMORY_DECAY_HALF_LIFE_DAYS", 30),
        web_search_url=env.get("AGENT_FRAMEWORK_WEB_SEARCH_URL"),
        web_search_query_param=env.get("AGENT_FRAMEWORK_WEB_SEARCH_QUERY_PARAM", "q"),
        web_search_headers=_env_json_dict(env, "AGENT_FRAMEWORK_WEB_SEARCH_HEADERS"),
        builder_llm=_llm_settings_from_env(env, "AGENT_FRAMEWORK_BUILDER"),
        research_llm=_llm_settings_from_env(env, "AGENT_FRAMEWORK_RESEARCH"),
        fea_llm=_llm_settings_from_env(env, "AGENT_FRAMEWORK_FEA"),
    )
    settings.ensure_storage_dirs()
    return settings


def _llm_settings_from_env(env: dict[str, str], prefix: str) -> LlmSettings:
    return LlmSettings(
        base_url=env.get(f"{prefix}_BASE_URL", DEFAULT_MIMO_BASE_URL),
        api_key=_first_env_value(
            env,
            f"{prefix}_API_KEY",
            "MIMO_API_KEY",
            "API_KEY",
            "OPENAI_API_KEY",
        ),
        model=env.get(f"{prefix}_MODEL", DEFAULT_MIMO_MODEL),
        streaming=_env_bool(env, f"{prefix}_STREAMING", True),
        temperature=_env_float(env, f"{prefix}_TEMPERATURE", 0.2),
        max_completion_tokens=_env_int(env, f"{prefix}_MAX_COMPLETION_TOKENS", 8192),
    )


def _first_env_value(env: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = env.get(key)
        if value:
            return value
    return ""


def _env_bool(env: dict[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(env: dict[str, str], key: str, default: int) -> int:
    value = env.get(key)
    if value is None:
        return default
    return int(value)


def _env_float(env: dict[str, str], key: str, default: float) -> float:
    value = env.get(key)
    if value is None:
        return default
    return float(value)


def _env_json_dict(env: dict[str, str], key: str) -> Dict[str, str]:
    value = env.get(key)
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError(f"{key} must be a JSON object")
    return {str(item_key): str(item_value) for item_key, item_value in parsed.items()}
