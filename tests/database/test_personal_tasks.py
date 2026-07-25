from __future__ import annotations

from datetime import date

from personal_agent.memory import SQLiteAgentRepository


def test_independent_daily_and_weekly_tasks(
    repository: SQLiteAgentRepository,
) -> None:
    week_start = date(2026, 7, 20)
    daily_id = repository.add_personal_task(
        "今天阅读一章",
        week_start,
        "day",
        date(2026, 7, 25),
    )
    weekly_id = repository.add_personal_task(
        "本周完成练习",
        week_start,
        "week",
    )

    tasks = repository.tasks_for_week(week_start)
    assert {item["scope"] for item in tasks} == {"day", "week"}
    assert all(item["goal_id"] is None for item in tasks)
    assert daily_id < 0
    assert weekly_id < 0

    assert repository.set_task_completed(daily_id, True)
    updated = repository.tasks_for_week(week_start)
    assert next(item for item in updated if item["id"] == daily_id)["completed"]
