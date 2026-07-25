from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Callable, Protocol

from personal_agent.agent.risk import RiskAnalyzer
from personal_agent.agent.task import TaskPlan
from personal_agent.agent.task import TaskStep


@dataclass(frozen=True)
class ReviewDecision:
    approved: bool
    reviewer: str = "user"
    reason: str = ""


class PlanReviewer(Protocol):
    """Replaceable user-review boundary for CLI or a future Web UI."""

    def review(self, plan: TaskPlan) -> ReviewDecision: ...


class CLIReviewer:
    def __init__(
        self,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
        preview_fn: Callable[[TaskStep], str | None] | None = None,
    ) -> None:
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.preview_fn = preview_fn

    def review(self, plan: TaskPlan) -> ReviewDecision:
        self.output_fn("=== Agent 执行计划 ===")
        self.output_fn(f"任务 ID：{plan.task_id}")
        self.output_fn(f"目标：{plan.goal}")
        for step in plan.steps:
            self.output_fn(
                f"\n{step.id}. {step.description}\n"
                f"   工具：{step.tool}\n"
                f"   风险：{step.risk}/10（{RiskAnalyzer.label(step.risk)}）\n"
                f"   参数：{json.dumps(step.arguments, ensure_ascii=False)}"
            )
            if self.preview_fn is not None:
                preview = self.preview_fn(step)
                if preview:
                    self.output_fn(f"   预览：\n{preview}")
        answer = self.input_fn(
            "\n是否按以上精确计划执行？请输入 yes："
        ).strip().casefold()
        if answer == "yes":
            return ReviewDecision(True)
        return ReviewDecision(False, reason="用户取消计划")
