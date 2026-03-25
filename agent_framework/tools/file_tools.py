import os
from langchain_core.tools import tool

@tool
def read_local_file(file_path: str) -> str:
    """Read the content of a local file.
    
    Args:
        file_path: The path to the file to read.
    """
    try:
        # Security: restrict to project directory (optional for MVP but good practice)
        # For simplicity, we just read it
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        # Check if it's an image file
        if file_path.lower().strip().endswith(('.png', '.jpg', '.jpeg')):
            # For images, we return the absolute path to trigger the multimodal workflow logic
            # The workflow.py will detect this path and convert it to a multimodal message
            return os.path.abspath(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

@tool
def list_directory(directory_path: str = ".") -> str:
    """List the contents of a directory.
    
    Args:
        directory_path: The path to the directory to list. Defaults to current directory.
    """
    try:
        items = os.listdir(directory_path)
        return "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"
