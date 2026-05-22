import uuid

from langchain_openai import ChatOpenAI

from agent_framework.agents import create_research_agent
from agent_framework.config import get_settings
from agent_framework.core import Gateway


def build_llm() -> ChatOpenAI:
    llm_settings = get_settings().research_llm
    if not llm_settings.api_key:
        raise RuntimeError(
            "missing research model api key in .env: set "
            "AGENT_FRAMEWORK_RESEARCH_API_KEY, MIMO_API_KEY, API_KEY, or OPENAI_API_KEY"
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


def start_chat() -> None:
    gateway = Gateway()
    spec, tools = create_research_agent(build_llm(), gateway.settings)
    gateway.register_agent(spec, tools)

    session_id = str(uuid.uuid4())
    print(f"=== Connected to {spec.name} ===")
    print(f"Session: {session_id}")
    print("(输入 'exit' 或 'quit' 退出)\n")

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
    start_chat()
