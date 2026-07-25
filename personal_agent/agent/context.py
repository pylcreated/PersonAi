from __future__ import annotations

from datetime import datetime
from typing import Callable

from personal_agent.core.agent import week_start
from personal_agent.core.clock import local_now
from personal_agent.core.ports import ConversationMemory


class PlanningContextProvider:
    """Read-only planning context backed by the existing Memory boundary."""

    def __init__(
        self,
        memory: ConversationMemory,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.memory = memory
        self.clock = clock

    def __call__(self, query: str) -> str:
        now = self.clock()
        context = self.memory.conversation_context(
            today=now.date(),
            week_start=week_start(now.date()),
            query=query,
        )
        sections = [
            "长期目标：\n"
            + (
                "\n".join(
                    f"- [{item['id']}] {item['title']}"
                    for item in context.goals
                )
                or "- 无"
            ),
            "本周任务：\n"
            + (
                "\n".join(
                    f"- [{'已完成' if item['completed'] else '未完成'}] "
                    f"{item['description']}"
                    for item in context.tasks
                )
                or "- 无"
            ),
            "用户确认的相关长期记忆：\n"
            + (
                "\n".join(
                    f"- [{item['type']}] {item['content']}"
                    for item in context.memories
                )
                or "- 无"
            ),
            "最近每日摘要：\n"
            + (
                "\n".join(
                    f"- {item['analysis_date']}: {item['summary']}"
                    for item in context.recent_analyses[:3]
                )
                or "- 无"
            ),
        ]
        return "\n\n".join(sections)
