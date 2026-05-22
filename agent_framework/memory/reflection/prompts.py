"""反思和经验提炼的LLM提示模板。"""

from langchain_core.messages import HumanMessage

REFLECTION_PROMPT_TEMPLATE = """分析以下对话执行轨迹，提取结构化洞察。

## 对话内容
{conversation}

## 工具调用结果
{tool_results}

## 任务摘要
{summary}

## 要求
请分析这次执行，提取：
1. 任务完成情况（success/partial/failure）
2. 程序性经验：如何完成特定任务的步骤
3. 情景记忆：特定上下文中的成功/失败案例
4. 用户偏好：观察到的用户习惯
5. 经验教训：一般性的经验或警告

输出JSON格式：
{{
  "outcome": "success|partial|failure",
  "procedures": [
    {{
      "task_pattern": "任务模式描述",
      "steps": ["步骤1", "步骤2", ...],
      "content": "完整的程序性经验描述",
      "confidence": 0.5
    }}
  ],
  "episodes": [
    {{
      "context_summary": "上下文摘要",
      "outcome": "success|failure|partial",
      "key_factors": ["关键因素1", "关键因素2", ...],
      "content": "完整的情景记忆描述",
      "confidence": 0.5
    }}
  ],
  "preferences": [
    {{
      "category": "language|style|workflow|tool_preference",
      "content": "用户偏好描述",
      "evidence": ["证据1", "证据2", ...],
      "confidence": 0.5
    }}
  ],
  "lessons": ["经验教训1", "经验教训2", ...]
}}

只输出JSON，不要其他内容。"""


def build_reflection_prompt(
    conversation: str,
    tool_results: str,
    summary: str,
) -> HumanMessage:
    """构建反思提示。"""
    return HumanMessage(
        content=REFLECTION_PROMPT_TEMPLATE.format(
            conversation=conversation,
            tool_results=tool_results,
            summary=summary,
        )
    )
