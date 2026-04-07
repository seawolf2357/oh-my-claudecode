"""Base tool class for AI-Scientist tools."""

from typing import List, Dict, Optional


class BaseTool:
    """Base class for all tools used by the AI-Scientist agent."""

    def __init__(self, name: str, description: str, parameters: List[Dict]):
        self.name = name
        self.description = description
        self.parameters = parameters

    def use_tool(self, **kwargs) -> Optional[str]:
        raise NotImplementedError("Subclasses must implement use_tool()")

    def get_tool_description(self) -> str:
        params_str = ", ".join(
            f"{p['name']}: {p['type']}" for p in self.parameters
        )
        return f"{self.name}({params_str}): {self.description}"
