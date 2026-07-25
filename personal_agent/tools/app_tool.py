from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from personal_agent.core.agent import week_start
from personal_agent.memory.repository import AgentRepository
from personal_agent.tools.base import ToolAuthorization, ToolResult
from personal_agent.tools.registry import ToolRegistry


@dataclass
class ListGoalsTool:
    repository: AgentRepository
    database_path: Path
    name: str = "list_goals"
    description: str = "查看用户现有的长期目标及其数字 ID"
    required_permission: str = "read"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        return [ToolAuthorization("read", str(self.database_path))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        goals = self.repository.active_goals()
        return ToolResult(
            True,
            json.dumps(goals, ensure_ascii=False, default=str),
            {"count": len(goals), "goals": goals},
        )


@dataclass
class ListTasksTool:
    repository: AgentRepository
    database_path: Path
    today: date
    name: str = "list_tasks"
    description: str = "查看当前任务清单，包含任务 ID、目标关联和完成状态"
    required_permission: str = "read"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        return [ToolAuthorization("read", str(self.database_path))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        tasks = self.repository.tasks_for_week(week_start(self.today))
        return ToolResult(
            True,
            json.dumps(tasks, ensure_ascii=False, default=str),
            {"count": len(tasks), "tasks": tasks},
        )


@dataclass
class CreateGoalTool:
    repository: AgentRepository
    database_path: Path
    name: str = "create_goal"
    description: str = "创建一个新的长期目标"
    required_permission: str = "write"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {"title": "string"}

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        title = str(arguments.get("title") or "").strip()
        if not title:
            raise ValueError("title 不能为空")
        return [ToolAuthorization("write", str(self.database_path))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        title = str(arguments["title"]).strip()
        goal_id = self.repository.add_goal(title)
        return ToolResult(
            True,
            f"已创建长期目标 #{goal_id}：{title}",
            {"goal_id": goal_id, "title": title},
        )


@dataclass
class AddGoalTaskTool:
    repository: AgentRepository
    database_path: Path
    today: date
    name: str = "add_goal_task"
    description: str = "在指定长期目标下添加一条本周任务；多条任务需分别调用"
    required_permission: str = "write"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {
            "goal_id": "integer",
            "description": "string",
        }

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        goal_id = int(arguments["goal_id"])
        description = str(arguments.get("description") or "").strip()
        if goal_id <= 0 or not description:
            raise ValueError("goal_id 和 description 必须有效")
        return [ToolAuthorization("write", str(self.database_path))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        goal_id = int(arguments["goal_id"])
        description = str(arguments["description"]).strip()
        start = week_start(self.today)
        existing = self.repository.tasks_for_week(start)
        duplicate = next(
            (
                item
                for item in existing
                if item.get("goal_id") == goal_id
                and str(item["description"]).strip().casefold()
                == description.casefold()
            ),
            None,
        )
        if duplicate is not None:
            return ToolResult(
                True,
                f"任务已存在，未重复添加：{description}",
                {"task_id": duplicate["id"], "created": False},
            )
        task_id = self.repository.add_task(goal_id, description, start)
        return ToolResult(
            True,
            f"已添加任务 #{task_id}：{description}",
            {
                "task_id": task_id,
                "goal_id": goal_id,
                "description": description,
                "created": True,
            },
        )


@dataclass
class SetTaskCompletedTool:
    repository: AgentRepository
    database_path: Path
    name: str = "set_task_completed"
    description: str = "按任务数字 ID 将任务标记为已完成或未完成"
    required_permission: str = "write"
    input_schema: Mapping[str, object] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.input_schema = {
            "task_id": "integer",
            "completed": "string，true 或 false",
        }

    def authorizations(self, arguments: dict[str, Any]) -> list[ToolAuthorization]:
        int(arguments["task_id"])
        self._completed(arguments)
        return [ToolAuthorization("write", str(self.database_path))]

    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        task_id = int(arguments["task_id"])
        completed = self._completed(arguments)
        if not self.repository.set_task_completed(task_id, completed):
            return ToolResult(False, f"没有找到任务 #{task_id}")
        label = "已完成" if completed else "未完成"
        return ToolResult(
            True,
            f"任务 #{task_id} 已标记为{label}",
            {"task_id": task_id, "completed": completed},
        )

    @staticmethod
    def _completed(arguments: dict[str, Any]) -> bool:
        raw = str(arguments.get("completed") or "").strip().casefold()
        if raw not in {"true", "false"}:
            raise ValueError("completed 必须是 true 或 false")
        return raw == "true"


def register_app_tools(
    registry: ToolRegistry,
    repository: AgentRepository,
    database_path: str | Path,
    today: date,
) -> None:
    path = Path(database_path).resolve()
    registry.register(ListGoalsTool(repository, path))
    registry.register(ListTasksTool(repository, path, today))
    registry.register(CreateGoalTool(repository, path))
    registry.register(AddGoalTaskTool(repository, path, today))
    registry.register(SetTaskCompletedTool(repository, path))
