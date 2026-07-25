from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from personal_agent.agent.executor import Executor
from personal_agent.agent.planner import Planner
from personal_agent.agent.reviewer import PlanReviewer
from personal_agent.agent.risk import RiskAnalyzer
from personal_agent.agent.state import TaskStateStore
from personal_agent.agent.task import TaskPlan
from personal_agent.core.clock import local_now


@dataclass(frozen=True)
class OrchestrationResult:
    task_id: str
    status: str
    message: str
    plan: TaskPlan


class AgentOrchestrator:
    """Finite plan-review-execute loop. It never elevates permissions or replans."""

    def __init__(
        self,
        planner: Planner,
        risk: RiskAnalyzer,
        reviewer: PlanReviewer,
        executor: Executor,
        state: TaskStateStore,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.planner = planner
        self.risk = risk
        self.reviewer = reviewer
        self.executor = executor
        self.state = state
        self.clock = clock

    def run(self, user_input: str) -> OrchestrationResult:
        plan = self.risk.analyze(self.planner.create_plan(user_input))
        self._save(plan, "pending_review")

        decision = self.reviewer.review(plan)
        if not decision.approved:
            self._save(plan, "cancelled")
            return OrchestrationResult(
                plan.task_id,
                plan.status,
                decision.reason or "任务已取消，未执行任何工具。",
                plan,
            )

        self._save(plan, "approved")
        self._save(plan, "running")
        for step in plan.steps:
            plan.current_step = step.id
            step.status = "running"
            self._touch(plan)
            self.state.save(plan)

            result = self.executor.execute(
                step,
                user_confirmed=True,
            )
            step.result = {
                "success": result.success,
                "content": result.content[:10000],
                "metadata": result.metadata,
            }
            if not result.success:
                step.status = "failed"
                self._save(plan, "failed")
                return OrchestrationResult(
                    plan.task_id,
                    plan.status,
                    f"步骤 {step.id} 执行失败，任务已停止：{result.content}",
                    plan,
                )
            step.status = "completed"
            self._touch(plan)
            self.state.save(plan)

        plan.current_step = None
        self._save(plan, "completed")
        return OrchestrationResult(
            plan.task_id,
            plan.status,
            "任务已按审核计划执行完成。",
            plan,
        )

    def _save(self, plan: TaskPlan, status: str) -> None:
        plan.status = status
        self._touch(plan)
        self.state.save(plan)

    def _touch(self, plan: TaskPlan) -> None:
        plan.updated_at = self.clock().isoformat()
