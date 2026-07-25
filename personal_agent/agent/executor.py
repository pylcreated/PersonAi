from __future__ import annotations

from personal_agent.agent.task import TaskStep
from personal_agent.tools import ToolCall, ToolManager, ToolResult


class Executor:
    """Dispatches one approved step through ToolManager only."""

    def __init__(self, tool_manager: ToolManager) -> None:
        self.tool_manager = tool_manager

    def execute(
        self,
        step: TaskStep,
        *,
        user_confirmed: bool,
    ) -> ToolResult:
        return self.tool_manager.execute(
            ToolCall(step.tool, step.arguments),
            actor="agent",
            user_confirmed=user_confirmed,
        )
