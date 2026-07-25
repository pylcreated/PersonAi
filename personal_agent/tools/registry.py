from __future__ import annotations

from personal_agent.tools.base import Tool


class ToolRegistry:
    """Registers tool capabilities without deciding whether they may run."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已注册：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def descriptions(self) -> list[dict[str, object]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "required_permission": tool.required_permission,
                "input_schema": dict(tool.input_schema),
            }
            for tool in self._tools.values()
        ]
