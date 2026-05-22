from __future__ import annotations

import uuid
from pathlib import Path

from langchain_openai import ChatOpenAI

from agent_framework.agents import create_technical_interview_assistant_agent
from agent_framework.config.settings import FrameworkSettings
from agent_framework.core import Gateway


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def main() -> None:
    root = Path(__file__).resolve().parent
    settings = FrameworkSettings(
        workspace_root=root,
        storage_root=root / ".runtime",
        database_path=root / ".runtime" / "runtime.db",
    )
    gateway = Gateway(settings)
    spec, tools = create_technical_interview_assistant_agent(build_llm(), settings)
    gateway.register_agent(spec, tools)

    session_id = str(uuid.uuid4())
    print(f"=== Connected to {spec.name} ===")
    print(f"Session: {session_id}")
    print("输入 exit 退出。")

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        response = gateway.run(
            agent_id=spec.agent_id,
            user_input=user_input,
            session_id=session_id,
        )
        print(f"\n{spec.name}:\n{response}")


if __name__ == "__main__":
    main()
