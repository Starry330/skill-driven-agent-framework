"""验证型工具执行节点。

拦截 LLM 调用不可见工具的请求，返回错误 ToolMessage，
合法调用正常执行。用于配合动态工具可见性功能。
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from langchain_core.messages import AIMessage, ToolMessage


def validate_tool_calls(
    state: Dict[str, Any],
    tool_executor_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    """在执行前验证 tool_calls 是否在可见工具范围内。

    Args:
        state: 当前 WorkflowState 快照。
        tool_executor_fn: 实际执行工具调用的函数（通常是 nodes.tools 的内部实现）。

    Returns:
        包含 messages 更新的字典。
    """
    visible_tools = set(state.get("visible_tool_names", []))
    if not visible_tools:
        return tool_executor_fn(state)

    messages = state.get("messages", [])
    if not messages:
        return tool_executor_fn(state)

    last_message = messages[-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return tool_executor_fn(state)

    valid_calls = [tc for tc in last_message.tool_calls if tc["name"] in visible_tools]
    invalid_calls = [tc for tc in last_message.tool_calls if tc["name"] not in visible_tools]

    if not invalid_calls:
        return tool_executor_fn(state)

    error_messages = [
        ToolMessage(
            content=(
                f"Error: Tool '{tc['name']}' is not available in the "
                f"current context. No active skill has declared this tool. "
                f"Available tools: {sorted(visible_tools)}"
            ),
            tool_call_id=tc["id"],
            name=tc["name"],
        )
        for tc in invalid_calls
    ]

    if not valid_calls:
        return {"messages": error_messages}

    # 混合场景：过滤掉非法调用，执行合法调用，再追加错误消息
    filtered_msg = AIMessage(
        content=last_message.content,
        additional_kwargs=last_message.additional_kwargs,
        tool_calls=valid_calls,
        id=last_message.id,
    )
    modified_messages = list(messages)
    for i, msg in enumerate(modified_messages):
        if msg is last_message:
            modified_messages[i] = filtered_msg
            break

    modified_state = dict(state)
    modified_state["messages"] = modified_messages
    result = tool_executor_fn(modified_state)

    result_messages = result.get("messages", [])
    result["messages"] = result_messages + error_messages
    return result
