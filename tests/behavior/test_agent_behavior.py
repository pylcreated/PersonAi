from __future__ import annotations

import json
from pathlib import Path

import pytest

from personal_agent.agent import (
    AgentOrchestrator,
    CLIReviewer,
    Executor,
    Planner,
    ReviewDecision,
    RiskAnalyzer,
)
from personal_agent.interfaces.cli import LocalCLI
from personal_agent.tools import ToolCall


class PlanningLLM:
    model_name = "planning-test"

    def __init__(self, payload: object = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[tuple[str, bool]] = []

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((prompt, json_mode))
        if self.error is not None:
            raise self.error
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload, ensure_ascii=False)


class DecisionReviewer:
    def __init__(self, approved: bool) -> None:
        self.approved = approved
        self.plans: list[object] = []

    def review(self, plan: object) -> ReviewDecision:
        self.plans.append(plan)
        return ReviewDecision(self.approved, reason="用户拒绝" if not self.approved else "")


def build_orchestrator(tool_sandbox, llm, reviewer) -> AgentOrchestrator:
    return AgentOrchestrator(
        Planner(llm, tool_sandbox.registry),
        RiskAnalyzer(),
        reviewer,
        Executor(tool_sandbox.manager),
        tool_sandbox.task_state,
    )


@pytest.mark.behavior
def test_simple_read_task_follows_plan_review_execute(tool_sandbox) -> None:
    readme = tool_sandbox.workspace / "README.md"
    readme.write_text("hello agent", encoding="utf-8")
    reviewer = DecisionReviewer(True)
    orchestrator = build_orchestrator(
        tool_sandbox,
        PlanningLLM(
            {
                "goal": "读取 README",
                "steps": [
                    {
                        "tool": "read_file",
                        "description": "读取 README 文件",
                        "arguments": {"path": str(readme)},
                    }
                ],
            }
        ),
        reviewer,
    )

    result = orchestrator.run("读取README文件")

    assert len(reviewer.plans) == 1
    assert result.status == "completed"
    assert result.plan.steps[0].tool == "read_file"
    assert result.plan.steps[0].result["content"] == "hello agent"
    assert tool_sandbox.audit.recent()[0]["actor"] == "agent"


@pytest.mark.behavior
def test_multi_step_task_preserves_order(tool_sandbox) -> None:
    source = tool_sandbox.workspace / "today.md"
    source.write_text("学习了 pytest", encoding="utf-8")
    summary = tool_sandbox.workspace / "summary.md"
    html = tool_sandbox.workspace / "summary.html"
    tools = ["search_file", "read_file", "create_file", "convert_file"]
    payload = {
        "goal": "整理今天学习笔记",
        "steps": [
            {
                "tool": "search_file",
                "description": "搜索学习笔记",
                "arguments": {
                    "keyword": "today",
                    "root": str(tool_sandbox.workspace),
                },
            },
            {
                "tool": "read_file",
                "description": "读取今日笔记",
                "arguments": {"path": str(source)},
            },
            {
                "tool": "create_file",
                "description": "创建总结",
                "arguments": {
                    "path": str(summary),
                    "content": "# 总结\n学习了 pytest",
                },
            },
            {
                "tool": "convert_file",
                "description": "转换总结",
                "arguments": {
                    "source": str(summary),
                    "target": str(html),
                },
            },
        ],
    }
    result = build_orchestrator(
        tool_sandbox,
        PlanningLLM(payload),
        DecisionReviewer(True),
    ).run("整理今天学习笔记")

    assert result.status == "completed"
    assert [step.tool for step in result.plan.steps] == tools
    assert [step.status for step in result.plan.steps] == ["completed"] * 4
    assert html.is_file()


@pytest.mark.behavior
def test_high_risk_delete_cannot_run_after_user_says_no(tool_sandbox) -> None:
    target = tool_sandbox.workspace / "duplicate.txt"
    target.write_text("keep until approved", encoding="utf-8")
    output: list[str] = []
    reviewer = CLIReviewer(
        input_fn=lambda prompt: "no",
        output_fn=output.append,
    )
    result = build_orchestrator(
        tool_sandbox,
        PlanningLLM(
            {
                "goal": "删除重复文件",
                "steps": [
                    {
                        "tool": "delete_file",
                        "description": "回收重复文件",
                        "arguments": {"path": str(target)},
                    }
                ],
            }
        ),
        reviewer,
    ).run("删除重复文件")

    assert result.status == "cancelled"
    assert result.plan.steps[0].risk == 9
    assert target.exists()
    assert tool_sandbox.audit.recent() == []
    assert any("风险：9/10（高）" in line for line in output)


@pytest.mark.behavior
@pytest.mark.parametrize(
    ("llm", "expected"),
    [
        (PlanningLLM("hello"), "Planner 没有返回 JSON"),
        (
            PlanningLLM(error=RuntimeError("LLM unavailable")),
            "LLM unavailable",
        ),
    ],
)
def test_cli_handles_planner_and_llm_failure_without_crashing(
    tool_sandbox,
    llm,
    expected,
    capsys,
) -> None:
    cli = LocalCLI.__new__(LocalCLI)
    cli.orchestrator = build_orchestrator(
        tool_sandbox,
        llm,
        DecisionReviewer(True),
    )
    cli.task_state = tool_sandbox.task_state

    cli._agent_command("run 测试异常")

    assert expected in capsys.readouterr().out
    assert tool_sandbox.task_state.list() == []


@pytest.mark.security
def test_planner_rejects_more_than_eight_steps(tool_sandbox) -> None:
    steps = [
        {
            "tool": "search_file",
            "description": f"搜索 {index}",
            "arguments": {"keyword": str(index)},
        }
        for index in range(9)
    ]
    orchestrator = build_orchestrator(
        tool_sandbox,
        PlanningLLM({"goal": "循环任务", "steps": steps}),
        DecisionReviewer(True),
    )

    with pytest.raises(ValueError, match="最多允许 8"):
        orchestrator.run("执行很多步骤")

    assert tool_sandbox.audit.recent() == []
    assert tool_sandbox.task_state.list() == []


@pytest.mark.scenario
def test_code_update_requires_diff_review_then_exact_approval(tool_sandbox) -> None:
    target = tool_sandbox.workspace / "main.py"
    target.write_text("print('old')\n", encoding="utf-8")
    payload = {
        "goal": "优化项目代码",
        "steps": [
            {
                "tool": "update_file",
                "description": "更新 main.py",
                "arguments": {
                    "path": str(target),
                    "content": "print('new')\n",
                },
            }
        ],
    }

    rejected_output: list[str] = []
    rejected_reviewer = CLIReviewer(
        input_fn=lambda prompt: "no",
        output_fn=rejected_output.append,
        preview_fn=lambda step: tool_sandbox.manager.preview(
            ToolCall(step.tool, step.arguments),
            actor="agent",
        ).content,
    )
    rejected = build_orchestrator(
        tool_sandbox,
        PlanningLLM(payload),
        rejected_reviewer,
    ).run("修改我的项目代码优化一下")
    assert rejected.status == "cancelled"
    assert target.read_text(encoding="utf-8") == "print('old')\n"
    assert any("-print('old')" in line for line in rejected_output)

    approved = build_orchestrator(
        tool_sandbox,
        PlanningLLM(payload),
        DecisionReviewer(True),
    ).run("按刚才的精确修改执行")
    assert approved.status == "completed"
    assert target.read_text(encoding="utf-8") == "print('new')\n"
    assert Path(
        str(approved.plan.steps[0].result["metadata"]["backup"])
    ).read_text(encoding="utf-8") == "print('old')\n"
