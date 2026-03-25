from typing import List
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

def summarize_history(messages: List[BaseMessage], llm: BaseChatModel, max_messages: int = 10) -> str:
    """
    Summarize a list of messages if it exceeds the max_messages threshold.
    Returns the summary string.
    """
    if len(messages) <= max_messages:
        # If not enough messages to summarize, just return a simple concatenation or empty string
        # depending on usage. But the prompt implies we want a summary of the *history*.
        # If it's short, maybe we don't need to summarize yet?
        # "This function should take a list of messages and return a summary string if the list is too long"
        # If it's not too long, what should it return?
        # Usually, if not summarizing, we might just return the original text or nothing.
        # But let's assume if it's short, we return an empty summary or just the text.
        # Given the instruction "return a summary string IF the list is too long", 
        # I'll assume we return an empty string if it's not long enough, 
        # or maybe the caller handles the logic.
        # But let's follow the instruction: "return a summary string if the list is too long".
        return ""

    # Create a prompt for summarization
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant that summarizes conversation history."),
        ("human", "Please summarize the following conversation history concisely, preserving key information and context:\n\n{conversation}")
    ])

    # Convert messages to string format for the prompt
    conversation_text = "\n".join([f"{msg.type}: {msg.content}" for msg in messages])

    chain = prompt | llm | StrOutputParser()
    
    summary = chain.invoke({"conversation": conversation_text})
    
    return summary
