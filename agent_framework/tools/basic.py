from langchain_core.tools import tool
from datetime import datetime

@tool
def calculator(expression: str) -> str:
    """Calculate the result of a mathematical expression.
    
    Args:
        expression: The mathematical expression to evaluate (e.g., '2 + 2').
    """
    try:
        # Using eval is generally unsafe but okay for a basic mock tool in a controlled environment
        # In production, use a safer math parser
        return str(eval(expression, {"__builtins__": None}, {}))
    except Exception as e:
        return f"Error calculating expression: {str(e)}"

@tool
def current_time() -> str:
    """Get the current time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
