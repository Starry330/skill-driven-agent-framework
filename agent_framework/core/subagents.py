"""子代理派生与结果回传。

这里先实现最小可用的子代理调用壳层：独立 session、最小 task brief 和工具白名单透传。更复杂的取消与调度可以继续挂在这一层扩展。
"""

from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SubagentRequest:
    """描述一次子代理调用请求。"""

    agent_id: str
    user_input: str
    parent_session_id: str
    task_brief: str
    tool_whitelist: list[str] | None = None
    timeout_seconds: int | None = None


@dataclass(slots=True)
class SubagentResult:
    """描述子代理执行完成后的标准返回。"""

    session_id: str
    status: str
    output: str


class SubagentManager:
    """负责派生独立子代理 session。

    子代理默认不继承主会话的全部上下文，只通过显式字段传入任务目标和
    允许工具列表，从接口上限制"隐式共享所有状态"的风险。
    """

    def __init__(self, gateway: "Gateway") -> None:
        self.gateway = gateway

    def _run_subagent(
        self,
        session_id: str,
        request: SubagentRequest,
    ) -> str:
        return self.gateway.run(
            agent_id=request.agent_id,
            user_input=request.user_input,
            session_id=session_id,
            task_brief=request.task_brief,
            tool_whitelist=request.tool_whitelist,
            parent_session_id=request.parent_session_id,
            subagent_mode=True,
        )

    def spawn(self, request: SubagentRequest) -> SubagentResult:
        """派生独立子代理 session。

        子代理必须使用独立 session_id，避免和父会话 transcript 混写。
        """
        session_id = str(uuid.uuid4())
        try:
            if request.timeout_seconds is not None:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._run_subagent, session_id, request)
                    response = future.result(timeout=request.timeout_seconds)
            else:
                response = self._run_subagent(session_id, request)
            return SubagentResult(session_id=session_id, status="completed", output=response)
        except FuturesTimeoutError:
            logger.warning("subagent_timeout", extra={"session_id": session_id, "agent_id": request.agent_id})
            return SubagentResult(
                session_id=session_id,
                status="failed",
                output=f"子代理执行超时（{request.timeout_seconds}秒）",
            )
        except Exception:
            logger.exception("subagent_failed", extra={"session_id": session_id, "agent_id": request.agent_id})
            return SubagentResult(
                session_id=session_id,
                status="failed",
                output="子代理执行失败，请查看日志了解详情",
            )
