"""Builder 子系统使用的数据模型。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


BUILDER_STATE_KEY = "builder"
BUILDER_CONFIRMATION_PHRASE = "确认创建"


class WorkspaceBlueprint(BaseModel):
    agents_md: str = ""
    soul_md: str = ""
    tools_md: str = ""
    user_md: str = ""
    memory_md: str = ""


class AgentRequirements(BaseModel):
    agent_name: str = ""
    agent_id: str = ""
    role: str = ""
    goal: str = ""
    style_constraints: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    user_constraints: list[str] = Field(default_factory=list)
    memory_requirements: list[str] = Field(default_factory=list)
    workflow_preferences: list[str] = Field(default_factory=list)


class SkillBlueprint(BaseModel):
    name: str
    description: str
    body: str
    triggers: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    input_schema: dict[str, object] = Field(default_factory=dict)
    output_schema: dict[str, object] = Field(default_factory=dict)
    decision_logic: list[dict[str, object]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    failure_modes: list[dict[str, object]] = Field(default_factory=list)
    fallback_strategy: list[dict[str, object]] = Field(default_factory=list)
    tool_policy: dict[str, object] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    availability_checks: list[str] = Field(default_factory=list)
    subagent_allowed: bool = False
    enabled: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)


class ToolBlueprint(BaseModel):
    name: str
    description: str
    reuse_existing: bool = True
    existing_tool_name: str | None = None
    reason: str = ""
    io_schema: dict[str, object] = Field(default_factory=dict)
    risk_level: str = "low"
    implementation_code: str = ""
    side_effect_level: str = "low"
    workspace_scope: str = "workspace"
    timeout_seconds: int = 30


class ToolPolicyBlueprint(BaseModel):
    allowlist: list[str] = Field(default_factory=list)
    denylist: list[str] = Field(default_factory=list)
    skill_tool_overrides: dict[str, list[str]] = Field(default_factory=dict)
    approval_required_for: list[str] = Field(default_factory=lambda: ["high", "critical"])


class NewToolPlanItem(BaseModel):
    name: str
    reason: str
    io_schema: dict[str, object] = Field(default_factory=dict)
    risk_level: str = "low"


class ToolPlan(BaseModel):
    reuse_tools: list[str] = Field(default_factory=list)
    new_tools: list[NewToolPlanItem] = Field(default_factory=list)


class AgentBlueprint(BaseModel):
    agent_id: str
    name: str
    role: str
    goal: str
    style_constraints: list[str] = Field(default_factory=list)
    workspace_docs: WorkspaceBlueprint = Field(default_factory=WorkspaceBlueprint)
    skills: list[SkillBlueprint] = Field(default_factory=list)
    tool_plan: list[ToolBlueprint] = Field(default_factory=list)
    tool_policy: ToolPolicyBlueprint = Field(default_factory=ToolPolicyBlueprint)
    memory_namespaces: list[str] = Field(
        default_factory=lambda: ["semantic", "episodic", "user_memory", "task_memory"]
    )
    workflow_name: str = "default"
    create_chat_entry: bool = True
    export_agent_factory: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class BuildResult(BaseModel):
    agent_id: str
    agent_dir: Path
    created_files: list[Path] = Field(default_factory=list)
    validation_messages: list[str] = Field(default_factory=list)
    chat_entry: Path | None = None
    factory_name: str
    status: str = "completed"
    message: str = ""


class BuilderSessionState(BaseModel):
    """Builder 在 `working_state[\"builder\"]` 下维护的会话状态。"""

    stage: str = "requirements_collection"
    pending_requirements: dict[str, Any] | None = None
    requirements_summary: str = ""
    pending_blueprint: dict[str, Any] | None = None
    pending_blueprint_summary: str = ""
    tool_plan: dict[str, Any] = Field(default_factory=dict)
    finalization_status: str = "draft"
    awaiting_confirmation: bool = False
    last_build_result: dict[str, Any] = Field(default_factory=dict)
