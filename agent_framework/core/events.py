"""运行时事件总线。

事件总线负责把 skill route、tool call、memory hit 等执行痕迹广播给日志、
存储或调试订阅方。它不做业务判断，只负责分发。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


@dataclass(slots=True)
class RuntimeEvent:
    """统一的运行时事件结构。"""

    event_type: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    """轻量事件分发器。

    当前实现是进程内同步广播，优先服务于审计、调试和 session 事件落盘。
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("agent_framework")
        self._subscribers: List[Callable[[RuntimeEvent], None]] = []

    def subscribe(self, callback: Callable[[RuntimeEvent], None]) -> None:
        self._subscribers.append(callback)

    def emit(self, event_type: str, payload: Dict[str, Any]) -> RuntimeEvent:
        # 先产生日志再分发，保证即使订阅方抛错，基础事件轨迹仍然可见。
        event = RuntimeEvent(event_type=event_type, payload=payload)
        self.logger.info("runtime_event", extra={"event_type": event_type, "payload": payload})
        for subscriber in self._subscribers:
            try:
                subscriber(event)
            except Exception:
                self.logger.exception(
                    "subscriber_error",
                    extra={"event_type": event_type, "subscriber": subscriber.__qualname__},
                )
        return event
