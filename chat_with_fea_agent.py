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
from langchain_core.tools import tool
import sys
import io
from examples.fea_agent.stp_analyzer import STPAnalyzerCN
from examples.fea_agent.stp_viewer import STPViewer
import os

# --- 模拟 FEA 专用工具 ---
@tool
def analyze_stp_file(file_path: str) -> str:
    """
    分析指定的 STP 文件并返回详细的几何拓扑报告字符串。
    
    Args:
        file_path: STP 文件的绝对或相对路径
        
    Returns:
        str: 详细的分析报告
    """
    # 捕获 stdout 输出
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout
    
    try:
        analyzer = STPAnalyzerCN(file_path)
        analyzer.run()
        report = new_stdout.getvalue()
    except Exception as e:
        report = f"STP 分析过程中出现错误: {str(e)}"
    finally:
        sys.stdout = old_stdout
    print(report)
    return report

@tool
def get_multiview(file_path: str) -> str:
    """Generate multiview images (orthographic views) for a CAD model.
    
    Args:
        file_path: Path to the .stp or .step file.
    """
    try:
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        viewer = STPViewer(file_path)
        # Use extract_features instead of extract_points (which was renamed/removed in the update)
        viewer.extract_features()
        
        # 保存图片到当前目录或指定目录
        output_path = f"{os.path.basename(file_path)}_multiview.png"
        viewer.generate_multiview(output_dir=".")
        
        # Return only the path to trigger multimodal injection
        return os.path.abspath(output_path)
    except Exception as e:
        return f"Error generating multiview: {str(e)}"

def start_fea_chat():
    # 1. 配置 LLM
    llm = ChatOpenAI(
        base_url="http://172.16.55.7:9025/v1",
        api_key="empty",
        model="Qwen3.5-122B-A10B",
        temperature=0.7, # 专家模式建议降低温度
        top_p=0.95,
        extra_body={
            "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    )

    # 2. 加载 FEA Agent 配置
    soul_loader = SoulLoader()
    # 指向新建的 fea_agent 目录
    soul = soul_loader.load("examples/fea_agent/soul.md")

    skill_registry = SkillRegistry()
    # 指向新建的 skills 目录
    skill_registry.load_directory("examples/fea_agent/skills")

    memory_system = PsychMem(LongTermMemory())
    
    # 3. 注册工具 (包含基础工具 + FEA 专用工具)
    tool_registry = LocalToolRegistry()
    tool_registry.register_tool(calculator)
    tool_registry.register_tool(current_time)
    tool_registry.register_tool(read_local_file)
    tool_registry.register_tool(list_directory)
    # 注册 FEA 技能所需的底层工具
    tool_registry.register_tool(analyze_stp_file)
    tool_registry.register_tool(get_multiview)
    
    mcp_client = MCPClient(tool_registry)

    # 4. 创建图
    graph = create_agent_graph(soul, skill_registry, memory_system, mcp_client, llm)

    # 5. 启动对话
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n=== 已连接到 {soul.role} ===")
    print(f"目标: {soul.goal}")
    print(f"已加载技能: {[s['name'] for s in skill_registry.list_skills()]}")
    print("(输入 'exit' 退出)\n")

    while True:
        user_input = input("User: ")
        if user_input.lower() in ["exit", "quit"]:
            break

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
        start_fea_chat()
    except Exception as e:
        print(f"\n发生错误: {e}")
