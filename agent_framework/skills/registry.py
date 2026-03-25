import os
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from ruamel.yaml import YAML
from .models import Skill

class SkillRegistry:
    """
    Registry for managing and accessing skills.
    """
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self.yaml = YAML(typ='safe')

    def register(self, path: str) -> Skill:
        """
        Registers a skill from a markdown file.
        
        Args:
            path: The path to the markdown file containing the skill definition.
            
        Returns:
            The loaded Skill object.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        frontmatter, body = self._parse_frontmatter(content)
        
        if not frontmatter:
             raise ValueError(f"No valid frontmatter found in {path}")

        # Validate required fields
        if 'name' not in frontmatter:
            raise ValueError(f"Skill file {path} missing 'name' in frontmatter")
            
        skill = Skill(
            name=frontmatter['name'],
            description=frontmatter.get('description', ''),
            parameters=frontmatter.get('parameters', {}),
            body=body.strip(),
            metadata=frontmatter.get('metadata', {})
        )
        
        self._skills[skill.name] = skill
        return skill

    def get_skill(self, name: str) -> Optional[Skill]:
        """
        Retrieves a skill by name.
        
        Args:
            name: The name of the skill to retrieve.
            
        Returns:
            The Skill object if found, else None.
        """
        return self._skills.get(name)

    def list_skills(self) -> List[Dict[str, str]]:
        """
        Lists all registered skills with their metadata.
        
        Returns:
            A list of dictionaries containing 'name' and 'description' for each skill.
        """
        return [
            {"name": skill.name, "description": skill.description}
            for skill in self._skills.values()
        ]

    def load_directory(self, path: str):
        """
        Recursively loads all skill files from a directory.
        
        Args:
            path: The directory path to search for skill files.
        """
        dir_path = Path(path)
        if not dir_path.exists() or not dir_path.is_dir():
             raise ValueError(f"Invalid directory path: {path}")
             
        for file_path in dir_path.rglob("*.md"):
            # Only load files named SKILL.md or those explicitly intended as skills
            # For now, let's restrict to SKILL.md or files in a direct 'skills' folder
            # to avoid loading resources/templates/etc.
            # A common pattern is that the skill file is named SKILL.md
            if file_path.name != "SKILL.md":
                continue

            try:
                self.register(str(file_path))
            except Exception as e:
                # Log error but continue loading other files
                print(f"Warning: Failed to load skill from {file_path}: {e}")

    def _parse_frontmatter(self, content: str) -> Tuple[Dict, str]:
        """
        Parses YAML frontmatter from markdown content.
        
        Args:
            content: The full content of the markdown file.
            
        Returns:
            A tuple of (frontmatter_dict, body_string).
        """
        # Simple frontmatter parser looking for --- at start
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                yaml_content = parts[1]
                body_content = parts[2]
                try:
                    frontmatter = self.yaml.load(yaml_content)
                    if isinstance(frontmatter, dict):
                        return frontmatter, body_content
                except Exception:
                    pass
        return {}, content
