"""工具执行器。

这里负责把 registry、policy、approval、audit 和 sandbox adapter 串成一条真正的
 工具治理链，而不是让 workflow 直接调用底层工具。
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from langchain_core.tools import BaseTool, StructuredTool

from agent_framework.tools.approval import ApprovalManager
from agent_framework.tools.audit import AuditLogger
from agent_framework.tools.models import ToolExecutionContext, ToolExecutionResult, ToolSpec
from agent_framework.tools.policy import ToolPolicy, ToolPolicyEngine
from agent_framework.tools.registry import ToolRegistry


class ToolExecutionError(RuntimeError):
    """对外暴露的统一工具执行异常。"""

    pass


class ToolExecutionTimeoutError(ToolExecutionError):
    """工具执行超时异常。"""

    pass


@dataclass(slots=True)
class SandboxAdapter:
    """受治理的执行适配器。

    当前默认实现是本地调用壳层，不声称提供 OS 级隔离，但保留统一接口供后续替换。
    """

    name: str = "governed-local"

    def execute(self, tool: ToolSpec, payload: Dict[str, Any]) -> Any:
        timeout = tool.timeout_seconds
        if timeout is not None and timeout > 0:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(tool.base_tool.invoke, payload)
                try:
                    return future.result(timeout=timeout)
                except FuturesTimeoutError:
                    raise ToolExecutionTimeoutError(
                        f"工具 {tool.name} 执行超时（{timeout}秒）"
                    ) from None
        return tool.base_tool.invoke(payload)


class ToolExecutor:
    """串联工具治理各环节的执行器。"""

    def __init__(
        self,
        registry: ToolRegistry,
        policy_engine: ToolPolicyEngine,
        approval_manager: ApprovalManager,
        audit_logger: AuditLogger,
        sandbox_adapter: SandboxAdapter | None = None,
    ) -> None:
        self.registry = registry
        self.policy_engine = policy_engine
        self.approval_manager = approval_manager
        self.audit_logger = audit_logger
        self.sandbox_adapter = sandbox_adapter or SandboxAdapter()

    def execute(
        self,
        tool_name: str,
        payload: Dict[str, Any],
        context: ToolExecutionContext,
        policy: ToolPolicy,
    ) -> ToolExecutionResult:
        """执行一个工具调用，并产出统一结果结构。"""

        tool = self.registry.get(tool_name)
        if tool is None:
            raise ToolExecutionError(f"unknown tool: {tool_name}")

        decision = self.policy_engine.evaluate(tool, context, policy)
        if not decision.allowed:
            result = ToolExecutionResult(ok=False, denied=True, error=decision.reason)
            self.audit_logger.log(tool, context, result)
            return result

        if decision.approval_required:
            approval = self.approval_manager.approve(tool, context)
            if not approval.approved:
                result = ToolExecutionResult(
                    ok=False,
                    denied=True,
                    approval_required=True,
                    error=approval.reason or "approval denied",
                )
                self.audit_logger.log(tool, context, result)
                return result

        if context.dry_run:
            # dry-run 只验证路由和策略，不触碰真实副作用。
            result = ToolExecutionResult(ok=True, output={"dry_run": True, "tool": tool_name})
            self.audit_logger.log(tool, context, result)
            return result

        started = time.perf_counter()
        attempts = max(1, tool.retry_policy.attempts)
        last_error: str | None = None
        for attempt in range(attempts):
            try:
                output = self.sandbox_adapter.execute(tool, payload)
                result = ToolExecutionResult(
                    ok=True,
                    output=output,
                    metadata={
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                        "attempt": attempt + 1,
                    },
                )
                self.audit_logger.log(tool, context, result)
                return result
            except Exception as exc:  # noqa: BLE001
                # 工具异常统一收敛为结构化结果，避免直接把底层异常散到 workflow 层。
                last_error = str(exc)
                if attempt + 1 >= attempts:
                    break

        result = ToolExecutionResult(
            ok=False,
            error=last_error or "tool execution failed",
            metadata={"duration_ms": round((time.perf_counter() - started) * 1000, 2)},
        )
        self.audit_logger.log(tool, context, result)
        return result

    def build_langchain_tools(
        self,
        context: ToolExecutionContext,
        policy: ToolPolicy,
    ) -> List[BaseTool]:
        # 给 LLM 绑定的是“受治理包装后的工具”，不是 registry 中的原始 BaseTool。
        tools: List[BaseTool] = []
        for spec in self.registry.all():
            decision = self.policy_engine.evaluate(spec, context, policy)
            if not decision.allowed:
                continue
            args_schema = getattr(spec.base_tool, "args_schema", None)

            def make_function(tool_name: str) -> Callable[..., Any]:
                def _invoke(**kwargs: Any) -> Any:
                    result = self.execute(tool_name, kwargs, context, policy)
                    if not result.ok:
                        raise ToolExecutionError(result.error or f"tool failed: {tool_name}")
                    return result.output

                return _invoke

            tools.append(
                StructuredTool.from_function(
                    func=make_function(spec.name),
                    name=spec.name,
                    description=spec.description,
                    args_schema=args_schema,
                )
            )
        return tools

    def build_filtered_langchain_tools(
        self,
        context: ToolExecutionContext,
        policy: ToolPolicy,
        active_skills: List[str],
    ) -> tuple[List[BaseTool], List[str]]:
        """按活跃 skill 过滤工具，返回 (tools, visible_tool_names)。

        出现在 skill_tool_overrides 中的工具只在对应 skill 激活时可见；
        不在任何 override 中的工具始终可见（全局工具）。

        注意：不调用 policy_engine.evaluate() 做技能过滤，因为它内部的
        skill_tool_overrides 逻辑会排除全局工具。这里自行实现可见性判断。
        """
        all_override_tools: set[str] = set()
        for tools_list in policy.skill_tool_overrides.values():
            all_override_tools.update(tools_list)

        tools: List[BaseTool] = []
        visible_names: List[str] = []
        for spec in self.registry.all():
            # 基础策略检查（denylist、session whitelist、allowlist）
            if spec.name in policy.denylist:
                continue
            if context.tool_whitelist is not None and spec.name not in context.tool_whitelist:
                continue
            if policy.allowlist is not None and spec.name not in policy.allowlist:
                continue
            # 技能可见性：override 中的工具仅在对应 skill 激活时可见
            if spec.name in all_override_tools:
                belongs_to_active = any(
                    spec.name in policy.skill_tool_overrides.get(sn, [])
                    for sn in active_skills
                )
                if not belongs_to_active:
                    continue
            args_schema = getattr(spec.base_tool, "args_schema", None)

            def make_function(tool_name: str = spec.name) -> Callable[..., Any]:
                def _invoke(**kwargs: Any) -> Any:
                    result = self.execute(tool_name, kwargs, context, policy)
                    if not result.ok:
                        raise ToolExecutionError(result.error or f"tool failed: {tool_name}")
                    return result.output

                return _invoke

            tools.append(
                StructuredTool.from_function(
                    func=make_function(),
                    name=spec.name,
                    description=spec.description,
                    args_schema=args_schema,
                )
            )
            visible_names.append(spec.name)
        return tools, visible_names
