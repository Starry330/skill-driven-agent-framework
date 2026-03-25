import re
from typing import Dict, Any
from pathlib import Path
from ruamel.yaml import YAML
from .models import Soul, Guardrail

class SoulLoader:
    """Loads Soul configurations from markdown files."""

    def __init__(self):
        self.yaml = YAML(typ='safe')

    def load(self, path: str) -> Soul:
        """
        Loads a Soul instance from a markdown file with YAML frontmatter.

        Args:
            path: The path to the markdown file.

        Returns:
            A Soul instance populated with data from the file.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Soul file not found: {path}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, body = self._parse_frontmatter(content)
        
        # Parse guardrails if they exist in the frontmatter
        guardrails_data = frontmatter.get('guardrails', [])
        guardrails = []
        for g in guardrails_data:
            guardrails.append(Guardrail(**g))
        
        # Prepare data for Soul model
        soul_data = {
            'role': frontmatter.get('role'),
            'goal': frontmatter.get('goal'),
            'backstory': frontmatter.get('backstory'),
            'style': frontmatter.get('style', []),
            'guardrails': guardrails,
            'system_prompt': body.strip()
        }

        return Soul(**soul_data)

    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """
        Parses YAML frontmatter from markdown content.
        
        Returns:
            A tuple containing the parsed YAML dictionary and the remaining markdown body.
        """
        # Regex to match YAML frontmatter enclosed in ---
        # It looks for the start of the file, then ---, then content, then ---
        pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)
        match = pattern.match(content)

        if match:
            yaml_content = match.group(1)
            body_content = match.group(2)
            try:
                frontmatter = self.yaml.load(yaml_content)
                if not isinstance(frontmatter, dict):
                     # If the YAML is valid but not a dict (e.g. a list), treat as empty
                    return {}, content
                return frontmatter, body_content
            except Exception as e:
                 # If YAML parsing fails, you might want to log a warning or raise an error.
                 # For now, we'll raise an error to be explicit.
                 raise ValueError(f"Failed to parse YAML frontmatter: {e}")
        else:
            # If no frontmatter is found, return empty dict and full content as body
            # However, for Soul files, frontmatter is expected.
            # We can decide to return empty frontmatter or raise an error.
            # Let's return empty frontmatter and treat everything as body, 
            # but this will likely fail validation for required fields in Soul.
            return {}, content
