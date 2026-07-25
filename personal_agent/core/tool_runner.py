from __future__ import annotations

import re
from dataclasses import dataclass

from personal_agent.agent.planner import Planner
from personal_agent.tools import ToolCall, ToolManager


@dataclass(frozen=True)
class ToolRunSummary:
    reply: str
    executed: int
    succeeded: int


class ChatToolRunner:
    """Lets the model choose registered tools, then executes through ToolManager."""

    OPERATION_PATTERN = re.compile(
        r"(添加|加入|创建|新建|删除|修改|更新|标记|完成|安排|制定|规划|"
        r"保存|关联|查看|列出|查询).{0,16}(任务|目标|清单)"
        r"|(?:任务|目标|清单).{0,16}(添加|加入|创建|新建|删除|修改|更新|"
        r"标记|完成|安排|制定|规划|保存|关联|查看|列出|查询)"
    )

    def __init__(self, planner: Planner, manager: ToolManager) -> None:
        self.planner = planner
        self.manager = manager

    def should_handle(self, message: str) -> bool:
        return bool(self.OPERATION_PATTERN.search(message))

    def run(self, message: str) -> ToolRunSummary:
        try:
            plan = self.planner.create_plan(message)
        except Exception as exc:
            return ToolRunSummary(
                f"我理解了你的操作指令，但没有生成可执行的工具计划，因此没有修改数据。原因：{exc}",
                0,
                0,
            )

        lines: list[str] = []
        succeeded = 0
        for step in plan.steps:
            result = self.manager.execute(
                ToolCall(step.tool, step.arguments),
                actor="chat-agent",
                user_confirmed=True,
            )
            status = "成功" if result.success else "失败"
            lines.append(f"- {step.description}：{status}，{result.content}")
            if result.success:
                succeeded += 1
            else:
                break

        executed = len(lines)
        headline = (
            f"已通过 Tool 执行 {executed} 步，成功 {succeeded} 步。"
            if succeeded == executed
            else f"Tool 执行在第 {executed} 步停止，成功 {succeeded} 步。"
        )
        return ToolRunSummary(
            headline + ("\n" + "\n".join(lines) if lines else ""),
            executed,
            succeeded,
        )
