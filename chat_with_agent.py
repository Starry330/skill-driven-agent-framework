import uuid
from langchain_openai import ChatOpenAI
from agent_framework.soul.loader import SoulLoader
from agent_framework.skills.registry import SkillRegistry
from agent_framework.memory.psych_mem import PsychMem
from agent_framework.memory.long_term import LongTermMemory
from agent_framework.mcp.client import MCPClient
from agent_framework.tools.registry import LocalToolRegistry
from agent_framework.tools.basic import calculator, current_time
from agent_framework.tools.file_tools import read_local_file, list_directory
from agent_framework.core.graph import create_agent_graph

def start_chat():
    # 1. 配置 LLM (使用用户提供的参数)
    llm = ChatOpenAI(
        base_url="http://172.16.55.7:9025/v1",
        api_key="empty",
        model="Qwen3.5-122B-A10B",
        temperature=1,
        top_p=0.95,
        presence_penalty=1.5,
        extra_body={
            "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    )

    # 2. 初始化组件
    soul_loader = SoulLoader()
    soul = soul_loader.load("examples/research_agent/soul.md")

    skill_registry = SkillRegistry()
    skill_registry.load_directory("examples/research_agent/skills")

    memory_system = PsychMem(LongTermMemory())
    
    # --- 注册真实工具 ---
    tool_registry = LocalToolRegistry()
    tool_registry.register_tool(calculator) # 真实的数学计算工具
    tool_registry.register_tool(current_time) # 真实的时间获取工具
    tool_registry.register_tool(read_local_file) # 真实的本地文件读取工具
    tool_registry.register_tool(list_directory) # 真实的本地目录列表工具
    
    mcp_client = MCPClient(tool_registry)
    # ------------------

    # 3. 创建 Agent 图
    # 不开启 interrupt_before=["tools"] 以便顺畅对话，除非用户需要
    graph = create_agent_graph(soul, skill_registry, memory_system, mcp_client, llm)

    # 4. 对话循环
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"=== 已连接到 {soul.role} ===")
    print(f"目标: {soul.goal}")
    print("(输入 'exit' 或 'quit' 退出对话)\n")

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        # 运行流
        events = graph.stream(
            {"messages": [("user", user_input)]},
            config,
            stream_mode="values"
        )

        last_message = None
        for event in events:
            if "messages" in event:
                last_message = event["messages"][-1]
        
        if last_message and hasattr(last_message, "content"):
            print(f"\n{soul.role}: {last_message.content}\n")

if __name__ == "__main__":
    try:
        start_chat()
    except Exception as e:
        print(f"\n发生错误: {e}")
        print("请检查 API 地址是否可达。")
