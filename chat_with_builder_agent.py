import uuid

from langchain_openai import ChatOpenAI

from agent_framework.agents import create_builder_agent
from agent_framework.config import get_settings
from agent_framework.config.mimo_token_plan import preflight_mimo_token_plan
from agent_framework.core import Gateway


def build_llm() -> ChatOpenAI:
    llm_settings = get_settings().builder_llm
    if not llm_settings.api_key:
        raise RuntimeError(
            "missing builder model api key in .env: set "
            "AGENT_FRAMEWORK_BUILDER_API_KEY, MIMO_API_KEY, API_KEY, or OPENAI_API_KEY"
        )

    return ChatOpenAI(
        api_key=llm_settings.api_key,
        base_url=llm_settings.base_url,
        model=llm_settings.model,
        streaming=llm_settings.streaming,
        temperature=llm_settings.temperature,
        max_completion_tokens=llm_settings.max_completion_tokens,
        default_headers={
            "Authorization": f"Bearer {llm_settings.api_key}",
            "api-key": llm_settings.api_key,
        },
    )


def start_builder_chat() -> None:
    gateway = Gateway()
    llm = build_llm()
    preflight = preflight_mimo_token_plan(gateway.settings.builder_llm)
    spec, tools = create_builder_agent(llm, gateway.settings)
    gateway.register_agent(spec, tools)

    session_id = str(uuid.uuid4())
    print(f"=== {spec.name} 已连接 ===")
    print(f"会话: {session_id}")
    print(f"模型: {preflight.model}")
    print()
    print("你好！我是 Agent 构建助手。")
    print("告诉我你想创建什么样的 agent，我会帮你整理需求并生成完整脚手架。")
    print()
    print("你可以用任何方式描述你的想法，比如：")
    print('  - "我想创建一个能帮我搜索网页的研究助手"')
    print('  - "我需要一个面试助手，能模拟面试官提问"')
    print('  - "帮我做一个代码审查 agent"')
    print()
    print("只有在你确认 blueprint 后，才会真正写入文件。\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in {"exit", "quit"}:
            break
        print(f"\n{spec.name}: ", end="", flush=True)
        for event in gateway.stream(
            agent_id=spec.agent_id, user_input=user_input, session_id=session_id
        ):
            if event.event_type == "text_delta":
                print(event.payload.get("text", ""), end="", flush=True)
            elif event.event_type == "run_completed":
                print("\n")
            elif event.event_type == "run_failed":
                print(f"\n[run_failed] {event.payload.get('error', '未知错误')}\n")


if __name__ == "__main__":
    start_builder_chat()
