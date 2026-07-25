from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from personal_agent.agent import (
    AgentOrchestrator,
    Executor,
    JsonTaskStateStore,
    Planner,
    ReviewDecision,
    RiskAnalyzer,
)
from personal_agent.interfaces.cli import LocalCLI
from personal_agent.security import JsonlAuditSink, ScopedPermissionManager
from personal_agent.tools import ToolManager, ToolRegistry
from personal_agent.tools.file_tool import register_file_tools


class FakePlanningLLM:
    model_name = "fake-planner"

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, bool]] = []

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((prompt, json_mode))
        return json.dumps(self.payload, ensure_ascii=False)


class StubReviewer:
    def __init__(self, approved: bool) -> None:
        self.approved = approved
        self.reviewed = 0

    def review(self, plan: object) -> ReviewDecision:
        del plan
        self.reviewed += 1
        return ReviewDecision(
            self.approved,
            reason="" if self.approved else "用户拒绝",
        )


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        test_parent = Path(__file__).resolve().parent / ".test_agent_tmp"
        test_parent.mkdir(exist_ok=True)
        self.root = (test_parent / uuid4().hex).resolve()
        self.root.mkdir()
        self.addCleanup(
            self._cleanup,
            self.root,
            test_parent.resolve(),
        )
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state_root = self.workspace / ".personal_agent"

        self.registry = ToolRegistry()
        register_file_tools(
            self.registry,
            self.workspace,
            self.state_root,
        )
        permission = ScopedPermissionManager(self.workspace)
        self.audit = JsonlAuditSink(
            self.state_root / "audit" / "tools.jsonl"
        )
        self.tool_manager = ToolManager(
            self.registry,
            permission,
            self.audit,
        )
        self.state = JsonTaskStateStore(self.state_root / "tasks")

    @staticmethod
    def _cleanup(root: Path, expected_parent: Path) -> None:
        resolved = root.resolve()
        if resolved.parent != expected_parent:
            raise RuntimeError("拒绝清理测试范围之外的目录")
        shutil.rmtree(resolved, ignore_errors=True)

    def _orchestrator(
        self,
        payload: dict[str, object],
        approved: bool,
    ) -> tuple[AgentOrchestrator, FakePlanningLLM, StubReviewer]:
        llm = FakePlanningLLM(payload)
        reviewer = StubReviewer(approved)
        orchestrator = AgentOrchestrator(
            Planner(
                llm,
                self.registry,
                context_provider=lambda query: f"context:{query}",
            ),
            RiskAnalyzer(),
            reviewer,
            Executor(self.tool_manager),
            self.state,
        )
        return orchestrator, llm, reviewer

    def test_planner_uses_json_mode_tool_allowlist_and_local_risk(self) -> None:
        orchestrator, llm, reviewer = self._orchestrator(
            {
                "goal": "查找 Agent 文档",
                "steps": [
                    {
                        "tool": "search_file",
                        "description": "搜索文档",
                        "arguments": {"keyword": "Agent"},
                        "risk": 10,
                    }
                ],
            },
            approved=False,
        )
        result = orchestrator.run("查找我的 Agent 文档")
        self.assertEqual(result.plan.steps[0].risk, 1)
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(reviewer.reviewed, 1)
        self.assertTrue(llm.calls[0][1])
        self.assertIn("context:查找我的 Agent 文档", llm.calls[0][0])
        self.assertIn("search_file", llm.calls[0][0])

    def test_planner_rejects_unknown_tool_and_invalid_arguments(self) -> None:
        unknown, _, _ = self._orchestrator(
            {
                "goal": "危险任务",
                "steps": [
                    {
                        "tool": "run_shell",
                        "description": "运行命令",
                        "arguments": {"command": "whoami"},
                    }
                ],
            },
            approved=True,
        )
        with self.assertRaisesRegex(ValueError, "未注册工具"):
            unknown.run("运行命令")

        invalid, _, _ = self._orchestrator(
            {
                "goal": "读取文件",
                "steps": [
                    {
                        "tool": "read_file",
                        "description": "读取",
                        "arguments": {"wrong": "value"},
                    }
                ],
            },
            approved=True,
        )
        with self.assertRaisesRegex(ValueError, "未知参数"):
            invalid.run("读取文件")
        self.assertEqual(self.state.list(), [])

    def test_user_rejection_persists_cancelled_state_without_execution(self) -> None:
        target = self.workspace / "not-created.txt"
        orchestrator, _, _ = self._orchestrator(
            {
                "goal": "创建文件",
                "steps": [
                    {
                        "tool": "create_file",
                        "description": "创建文件",
                        "arguments": {
                            "path": str(target),
                            "content": "no",
                        },
                    }
                ],
            },
            approved=False,
        )
        result = orchestrator.run("创建文件")
        self.assertEqual(result.status, "cancelled")
        self.assertFalse(target.exists())
        saved = self.state.load(result.task_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved.status, "cancelled")  # type: ignore[union-attr]
        self.assertEqual(self.audit.recent(), [])

    def test_approved_plan_executes_in_order_and_persists_completion(self) -> None:
        target = self.workspace / "result.txt"
        orchestrator, _, _ = self._orchestrator(
            {
                "goal": "创建并读取结果",
                "steps": [
                    {
                        "tool": "create_file",
                        "description": "创建结果",
                        "arguments": {
                            "path": str(target),
                            "content": "done",
                        },
                    },
                    {
                        "tool": "read_file",
                        "description": "读取结果",
                        "arguments": {"path": str(target)},
                    },
                ],
            },
            approved=True,
        )
        result = orchestrator.run("创建并读取结果")
        self.assertEqual(result.status, "completed")
        self.assertEqual(
            [step.status for step in result.plan.steps],
            ["completed", "completed"],
        )
        self.assertEqual(result.plan.steps[1].result["content"], "done")
        saved = self.state.load(result.task_id)
        self.assertEqual(saved.status, "completed")  # type: ignore[union-attr]
        events = self.audit.recent()
        self.assertEqual([event["actor"] for event in events], ["agent", "agent"])
        self.assertTrue(all(event["approval"] == "user" for event in events))

    def test_failure_stops_remaining_steps_and_is_recoverable_from_state(self) -> None:
        missing = self.workspace / "missing.txt"
        should_not_exist = self.workspace / "later.txt"
        orchestrator, _, _ = self._orchestrator(
            {
                "goal": "先读后写",
                "steps": [
                    {
                        "tool": "read_file",
                        "description": "读取缺失文件",
                        "arguments": {"path": str(missing)},
                    },
                    {
                        "tool": "create_file",
                        "description": "不应执行",
                        "arguments": {
                            "path": str(should_not_exist),
                            "content": "unsafe continuation",
                        },
                    },
                ],
            },
            approved=True,
        )
        result = orchestrator.run("失败后停止")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.plan.steps[0].status, "failed")
        self.assertEqual(result.plan.steps[1].status, "pending")
        self.assertFalse(should_not_exist.exists())
        saved = self.state.load(result.task_id)
        self.assertEqual(saved.status, "failed")  # type: ignore[union-attr]
        self.assertEqual(len(orchestrator.planner.llm.calls), 1)

    def test_high_risk_delete_uses_plan_approval_and_moves_to_trash(self) -> None:
        target = self.workspace / "duplicate.txt"
        target.write_text("duplicate", encoding="utf-8")
        orchestrator, _, _ = self._orchestrator(
            {
                "goal": "回收重复文件",
                "steps": [
                    {
                        "tool": "delete_file",
                        "description": "回收重复文件",
                        "arguments": {"path": str(target)},
                    }
                ],
            },
            approved=True,
        )
        result = orchestrator.run("回收重复文件")
        self.assertEqual(result.plan.steps[0].risk, 9)
        self.assertEqual(result.status, "completed")
        self.assertFalse(target.exists())
        trash_id = result.plan.steps[0].result["metadata"]["trash_id"]
        self.assertTrue((self.state_root / "trash" / trash_id).is_dir())

    def test_cli_run_and_task_history_use_orchestrator_state(self) -> None:
        target = self.workspace / "cli.txt"
        orchestrator, _, _ = self._orchestrator(
            {
                "goal": "CLI 创建文件",
                "steps": [
                    {
                        "tool": "create_file",
                        "description": "创建 CLI 文件",
                        "arguments": {
                            "path": str(target),
                            "content": "cli",
                        },
                    }
                ],
            },
            approved=True,
        )
        cli = LocalCLI.__new__(LocalCLI)
        cli.orchestrator = orchestrator
        cli.task_state = self.state

        output = io.StringIO()
        with redirect_stdout(output):
            cli._agent_command("run 创建 CLI 文件")
            cli._agent_command("tasks")

        self.assertTrue(target.exists())
        self.assertIn("执行完成", output.getvalue())
        self.assertIn("最近 Agent 任务", output.getvalue())


if __name__ == "__main__":
    unittest.main()
