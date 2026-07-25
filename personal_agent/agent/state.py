from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Protocol

from personal_agent.agent.task import TaskPlan


class TaskStateStore(Protocol):
    def save(self, plan: TaskPlan) -> None: ...

    def load(self, task_id: str) -> TaskPlan | None: ...

    def list(self, limit: int = 20) -> list[TaskPlan]: ...


class JsonTaskStateStore:
    """One JSON file per task; replaceable by SQLite or another backend."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def save(self, plan: TaskPlan) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(plan.task_id)
        payload = json.dumps(
            plan.as_dict(),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.root,
            delete=False,
        ) as stream:
            stream.write(payload)
            temporary = Path(stream.name)
        os.replace(temporary, target)

    def load(self, task_id: str) -> TaskPlan | None:
        path = self._path(task_id)
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("任务状态文件必须是 JSON 对象")
        return TaskPlan.from_dict(value)

    def list(self, limit: int = 20) -> list[TaskPlan]:
        if not self.root.exists():
            return []
        paths = sorted(
            self.root.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )[: max(0, limit)]
        results: list[TaskPlan] = []
        for path in paths:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    results.append(TaskPlan.from_dict(value))
            except (OSError, ValueError, json.JSONDecodeError, KeyError):
                continue
        return results

    def _path(self, task_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", task_id):
            raise ValueError("task_id 无效")
        return self.root / f"{task_id}.json"
