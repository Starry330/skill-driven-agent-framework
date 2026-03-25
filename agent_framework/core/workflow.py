from typing import Dict, Any, List, Optional
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, RemoveMessage
from langchain_core.language_models import BaseChatModel
from agent_framework.core.state import AgentState
from agent_framework.soul.models import Soul
from agent_framework.skills.registry import SkillRegistry
from agent_framework.memory.psych_mem import PsychMem
from agent_framework.memory.compactor import summarize_history
from agent_framework.mcp.client import MCPClient
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, RemoveMessage, ToolMessage
import base64
import os

class WorkflowNodes:
    def __init__(self, soul: Soul, skills: SkillRegistry, memory: PsychMem, mcp: MCPClient, llm: BaseChatModel):
        self.soul = soul
        self.skills = skills
        self.memory = memory
        self.mcp = mcp
        self.llm = llm

    def retrieve(self, state: AgentState) -> Dict[str, Any]:
        """
        Retrieves relevant skills and memories based on the current context.
        Updates the context in the state.
        """
        messages = state.get("messages", [])
        context = state.get("context", {}).copy() # Ensure we don't modify in place if not intended, though here we return new dict
        
        # Determine context query from last message
        context_query = ""
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, BaseMessage):
                context_query = last_message.content
            elif isinstance(last_message, dict):
                context_query = last_message.get("content", "")
            else:
                context_query = str(last_message)
        
        if not context_query:
            return {"context": context}

        # Retrieve memories
        relevant_memories = self.memory.retrieve_relevant(context_query)
        
        # Retrieve skills
        # Simple implementation: list all skills
        skills_list = self.skills.list_skills()
        # Extract names and descriptions
        available_skills = [f"{s['name']}: {s['description']}" for s in skills_list]
        
        # Update context
        context["relevant_memories"] = relevant_memories
        context["available_skills"] = available_skills
        
        return {"context": context}


# ...

    def agent(self, state: AgentState) -> Dict[str, Any]:
        """
        Constructs the prompt and invokes the LLM.
        """
        messages = state.get("messages", [])
        context = state.get("context", {})
        summary = state.get("summary", "")
        
        # Construct system prompt
        system_prompt = self._construct_system_prompt(context)
        
        # Bind tools
        tools = self.mcp.get_tools()
        if tools:
            llm_with_tools = self.llm.bind_tools(tools)
        else:
            llm_with_tools = self.llm
        
        # Prepare messages
        # Start with SystemMessage
        formatted_messages = []
        
        # Combine system prompt and summary into ONE system message to avoid multiple system messages
        # and ensure it's at the beginning.
        full_system_content = system_prompt
        if summary:
            full_system_content += f"\n\nSummary of previous conversation: {summary}"
        
        formatted_messages.append(SystemMessage(content=full_system_content))
        
        # Add conversation history
        # Ensure that if messages contain SystemMessages (which they shouldn't in this framework's design, 
        # but for robustness), they are handled. 
        # Most importantly, OpenAI-compatible APIs like vLLM often enforce that 
        # the list of messages starts with a single SystemMessage or only contains User/AI messages after the first.
        for msg in messages:
            if isinstance(msg, SystemMessage):
                # Convert internal SystemMessages to HumanMessages or just append their content to avoid the error
                formatted_messages[0].content += f"\n\nAdditional context: {msg.content}"
            elif isinstance(msg, ToolMessage):
                # Check if ToolMessage content is an image path and convert to multimodal message
                # This assumes that if a tool returns a path ending in .png/.jpg, it's an image intended for the LLM
                content_str = str(msg.content)
                # Simple heuristic: if content looks like a file path and exists, try to load it
                if content_str.strip().lower().endswith(('.png', '.jpg', '.jpeg')) and os.path.exists(content_str.strip()):
                    try:
                        image_path = content_str.strip()
                        with open(image_path, "rb") as image_file:
                            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                        
                        # Create multimodal content
                        new_content = [
                            {
                                "type": "text",
                                "text": f"Tool execution result (image at {image_path}):"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{encoded_string}"
                                }
                            }
                        ]
                        
                        # IMPORTANT: Modifying ToolMessage content directly might break some LLM providers 
                        # if they expect string content for tool outputs.
                        # However, for multimodal agents, this is the standard way to feed back visual results.
                        # We create a new ToolMessage to avoid mutating the original message in history if needed,
                        # but here we want to update the stream.
                        
                        # Create a NEW ToolMessage with the multimodal content to replace the old one in this context
                        new_msg = ToolMessage(
                            content=new_content,
                            tool_call_id=msg.tool_call_id,
                            name=msg.name,
                            additional_kwargs=msg.additional_kwargs
                        )
                        formatted_messages.append(new_msg)
                    except Exception as e:
                        print(f"Failed to encode image from tool output: {e}")
                        formatted_messages.append(msg)
                else:
                    formatted_messages.append(msg)
            else:
                formatted_messages.append(msg)
        
        # Invoke LLM
        response = llm_with_tools.invoke(formatted_messages)
        
        return {"messages": [response]}

    def summarize(self, state: AgentState) -> Dict[str, Any]:
        """
        Summarizes the conversation history if it's too long.
        """
        messages = state.get("messages", [])
        summary = state.get("summary", "")
        
        # Summarize if more than 10 messages (arbitrary threshold)
        if len(messages) > 10:
            # Create a copy of messages to summarize, potentially including old summary
            messages_to_summarize = []
            if summary:
                messages_to_summarize.append(SystemMessage(content=f"Previous summary: {summary}"))
            # Summarize all but last 2
            messages_to_summarize.extend(messages[:-2]) 
            
            new_summary = summarize_history(messages_to_summarize, self.llm)
            
            if new_summary:
                # Remove summarized messages
                # Note: This assumes messages have IDs. If not, RemoveMessage won't work effectively
                # unless we rely on some other mechanism. LangGraph typically assigns IDs.
                messages_to_remove = []
                for m in messages[:-2]:
                    if hasattr(m, 'id') and m.id:
                         messages_to_remove.append(RemoveMessage(id=m.id))
                
                if messages_to_remove:
                    return {"summary": new_summary, "messages": messages_to_remove}
                else:
                    # If no IDs, just update summary
                    return {"summary": new_summary}
        
        return {}

    def _construct_system_prompt(self, context: Dict[str, Any]) -> str:
        """
        Constructs the system prompt from Soul and Context.
        """
        soul = self.soul
        
        prompt_parts = []
        prompt_parts.append(f"Role: {soul.role}")
        prompt_parts.append(f"Goal: {soul.goal}")
        prompt_parts.append(f"Backstory: {soul.backstory}")
        
        if soul.style:
            prompt_parts.append("\nStyle Guidelines:")
            for style in soul.style:
                prompt_parts.append(f"- {style}")
        
        if soul.guardrails:
            prompt_parts.append("\nGuardrails:")
            for guardrail in soul.guardrails:
                prompt_parts.append(f"- {guardrail.name}: {guardrail.description}")
                for rule in guardrail.rules:
                    prompt_parts.append(f"  * {rule}")

        # Add context from Retrieve
        if "relevant_memories" in context and context["relevant_memories"]:
             prompt_parts.append("\nRelevant Memories:")
             prompt_parts.append(context["relevant_memories"])
             
        if "available_skills" in context and context["available_skills"]:
            prompt_parts.append("\nAvailable Skills (Reference):")
            for skill in context["available_skills"]:
                prompt_parts.append(f"- {skill}")

        return "\n".join(prompt_parts)
