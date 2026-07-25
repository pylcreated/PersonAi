from __future__ import annotations

from datetime import date, timedelta

from personal_agent.llm.base import LLMClient
from personal_agent.memory.repository import AgentRepository


class WeeklyReviewService:
    """Builds weekly reports from durable daily analyses and tasks."""

    def __init__(
        self,
        repository: AgentRepository,
        llm: LLMClient,
    ) -> None:
        self.repository = repository
        self.llm = llm

    def generate(self, week_start: date) -> str:
        week_end = week_start + timedelta(days=6)
        analyses = self.repository.analyses_between(week_start, week_end)
        tasks = self.repository.tasks_for_week(week_start)
        if self.llm.model_name == "mock":
            return self._mock_report(analyses, tasks)
        return self.llm.complete(
            self._build_prompt(week_start, analyses, tasks)
        )

    @staticmethod
    def _build_prompt(
        week_start: date,
        analyses: list[dict[str, object]],
        tasks: list[dict[str, object]],
    ) -> str:
        analysis_text = "\n".join(
            (
                f"- [{item['analysis_date']}] 总结: {item['summary']}; "
                f"进展: {item['progress']}; "
                f"模式: {item['patterns']}; 下一步: {item['next_actions']}"
            )
            for item in analyses
        ) or "- 本周没有每日分析"
        task_text = "\n".join(
            (
                f"- 目标: {item['goal_title']}; 任务: {item['description']}; "
                f"完成: {'是' if item['completed'] else '否'}"
            )
            for item in tasks
        ) or "- 本周没有任务记录"

        return f"""
你是一个温和但有洞察力的个人成长教练。请基于事实生成本周报告。

要求：
1. 只依据提供的信息，不得编造。
2. 分为“关键进展总结”“值得关注的模式”“下周计划建议”三段。
3. 信息不足时明确写出“信息不足，无法进一步判断”。
4. 下周建议必须具体。

周起始日期：{week_start.isoformat()}

每日分析：
{analysis_text}

任务情况：
{task_text}
""".strip()

    @staticmethod
    def _mock_report(
        analyses: list[dict[str, object]],
        tasks: list[dict[str, object]],
    ) -> str:
        progress = [
            str(value)
            for item in analyses
            for value in item.get("progress", [])
        ]
        patterns = [
            str(value)
            for item in analyses
            for value in item.get("patterns", [])
        ]
        next_actions = [
            str(value)
            for item in analyses
            for value in item.get("next_actions", [])
        ]
        completed_count = sum(1 for item in tasks if item.get("completed"))
        progress_text = "；".join(progress) or "信息不足，无法进一步判断。"
        pattern_text = "；".join(patterns) or "信息不足，无法进一步判断。"

        if next_actions:
            plan_text = "；".join(next_actions)
        else:
            unfinished = [
                str(item["description"])
                for item in tasks
                if not item.get("completed")
            ]
            plan_text = (
                "优先继续未完成任务：" + "；".join(unfinished)
                if unfinished
                else "信息不足，无法进一步判断。"
            )

        return (
            "关键进展总结:\n"
            f"{progress_text}\n"
            f"本周任务完成情况：{completed_count}/{len(tasks)}。\n\n"
            "值得关注的模式:\n"
            f"{pattern_text}\n\n"
            "下周计划建议:\n"
            f"{plan_text}"
        )
