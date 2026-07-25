from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

STEP_STATUSES = {"pending", "running", "completed", "failed", "skipped"}
PLAN_STATUSES = {
    "pending_review",
    "cancelled",
    "approved",
    "running",
    "completed",
    "failed",
}


@dataclass
class TaskStep:
    id: int
    tool: str
    description: str
    arguments: dict[str, Any]
    risk: int = 0
    status: str = "pending"
    result: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "description": self.description,
            "arguments": self.arguments,
            "risk": self.risk,
            "status": self.status,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskStep":
        status = str(value.get("status", "pending"))
        if status not in STEP_STATUSES:
            raise ValueError(f"无效步骤状态：{status}")
        arguments = value.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("步骤 arguments 必须是对象")
        result = value.get("result")
        if result is not None and not isinstance(result, dict):
            raise ValueError("步骤 result 必须是对象或 null")
        return cls(
            id=int(value["id"]),
            tool=str(value["tool"]),
            description=str(value["description"]),
            arguments=arguments,
            risk=max(0, min(10, int(value.get("risk", 0)))),
            status=status,
            result=result,
        )


@dataclass
class TaskPlan:
    goal: str
    steps: list[TaskStep]
    user_input: str
    task_id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "pending_review"
    current_step: int | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now().astimezone().isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now().astimezone().isoformat()
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "user_input": self.user_input,
            "steps": [step.as_dict() for step in self.steps],
            "status": self.status,
            "current_step": self.current_step,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskPlan":
        status = str(value.get("status", "pending_review"))
        if status not in PLAN_STATUSES:
            raise ValueError(f"无效任务状态：{status}")
        raw_steps = value.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("任务 steps 必须是数组")
        return cls(
            task_id=str(value["task_id"]),
            goal=str(value["goal"]),
            user_input=str(value.get("user_input", value["goal"])),
            steps=[TaskStep.from_dict(item) for item in raw_steps],
            status=status,
            current_step=(
                int(value["current_step"])
                if value.get("current_step") is not None
                else None
            ),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
        )
