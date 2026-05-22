"""session 与 memory 的持久化数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class SessionRecord:
    """session 元数据。"""

    session_id: str
    agent_id: str
    status: str = "active"
    parent_session_id: str | None = None


@dataclass(slots=True)
class MemoryRecord:
    """长期记忆条目。"""

    namespace: str
    key: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    experience_type: str = ""
    confidence: float = 0.5
    usage_count: int = 0
    last_used_at: str | None = None
    tags: List[str] = field(default_factory=list)
    task_pattern: str = ""


@dataclass(slots=True)
class SessionStateRecord:
    """与 transcript 分离保存的会话状态。"""

    session_id: str
    summary: str = ""
    active_skills: List[str] = field(default_factory=list)
    working_state: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProceduralExperience:
    """程序性经验：如何完成特定任务的步骤。"""

    task_pattern: str
    steps: List[str]
    content: str
    confidence: float = 0.5


@dataclass(slots=True)
class EpisodicExperience:
    """情景记忆：特定上下文中的成功/失败案例。"""

    context_summary: str
    outcome: str  # success, failure, partial
    key_factors: List[str]
    content: str
    confidence: float = 0.5


@dataclass(slots=True)
class UserPreference:
    """用户偏好：用户的工作习惯、偏好、风格。"""

    category: str  # language, style, workflow, tool_preference
    content: str
    evidence: List[str]
    confidence: float = 0.5


@dataclass(slots=True)
class ReflectionResult:
    """反思结果：从执行轨迹中提取的结构化洞察。"""

    outcome: str  # success, partial, failure
    procedures: List[ProceduralExperience] = field(default_factory=list)
    episodes: List[EpisodicExperience] = field(default_factory=list)
    preferences: List[UserPreference] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
