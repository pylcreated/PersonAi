from __future__ import annotations

from datetime import date
from pathlib import Path

from personal_agent.agent import Planner
from personal_agent.core.tool_runner import ChatToolRunner
from personal_agent.security import JsonlAuditSink, ScopedPermissionManager
from personal_agent.tools import ToolManager, ToolRegistry
from personal_agent.tools.app_tool import register_app_tools


class PlanLLM:
    model_name = "plan-test"

    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[tuple[str, bool]] = []

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((prompt, json_mode))
        return self.payload


def test_chat_model_calls_registered_tools_and_links_tasks(
    repository,
    isolated_root: Path,
) -> None:
    goal_id = repository.add_goal("学习系统设计")
    database_path = isolated_root / "agent.db"
    database_path.touch()
    registry = ToolRegistry()
    register_app_tools(
        registry,
        repository,
        database_path,
        date(2026, 7, 25),
    )
    manager = ToolManager(
        registry,
        ScopedPermissionManager(isolated_root),
        JsonlAuditSink(isolated_root / "audit.jsonl"),
    )
    llm = PlanLLM(
        (
            '{"goal":"添加学习任务","steps":['
            '{"tool":"add_goal_task","description":"添加第一项",'
            f'"arguments":{{"goal_id":{goal_id},"description":"阅读 CAP 理论"}}}},'
            '{"tool":"add_goal_task","description":"添加第二项",'
            f'"arguments":{{"goal_id":{goal_id},"description":"总结核心要点"}}}}'
            "]}"
        )
    )
    runner = ChatToolRunner(Planner(llm, registry), manager)

    result = runner.run("请添加两项学习任务到目标中")
    tasks = repository.tasks_for_week(date(2026, 7, 20))

    assert result.executed == 2
    assert result.succeeded == 2
    assert len(tasks) == 2
    assert all(item["goal_id"] == goal_id for item in tasks)
    assert llm.calls[0][1] is True


def test_chat_tool_router_does_not_treat_normal_conversation_as_operation() -> None:
    runner = ChatToolRunner.__new__(ChatToolRunner)

    assert not runner.should_handle("我今天心情不太好")
    assert runner.should_handle("把这个任务标记为完成")
