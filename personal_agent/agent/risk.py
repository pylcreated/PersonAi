from __future__ import annotations

from personal_agent.agent.task import TaskPlan, TaskStep


class RiskAnalyzer:
    """Deterministic local risk rules; model-supplied risk is never trusted."""

    TOOL_RISK = {
        "read_file": 1,
        "search_file": 1,
        "create_file": 3,
        "convert_file": 3,
        "update_file": 5,
        "restore_file": 5,
        "delete_file": 9,
        "execute_code": 10,
    }

    def calculate(self, step: TaskStep) -> int:
        return self.TOOL_RISK.get(step.tool, 10)

    def analyze(self, plan: TaskPlan) -> TaskPlan:
        for step in plan.steps:
            step.risk = self.calculate(step)
        return plan

    @staticmethod
    def label(risk: int) -> str:
        if risk <= 3:
            return "低"
        if risk <= 7:
            return "中"
        return "高"
