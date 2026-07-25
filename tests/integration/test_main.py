from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import schedule

from personal_agent.analysis import DailyAnalysisService, WeeklyReviewService
from personal_agent.application import WorkflowScheduler
from personal_agent.config import settings as config_settings
from personal_agent.core import Agent, ContextBuilder
from personal_agent.interfaces.channel import LocalChannel
from personal_agent.interfaces.cli import LocalCLI
from personal_agent.llm.mock import MockLLMClient
from personal_agent.memory import (
    DailyMemoryAnalyzer,
    MemoryManager,
    SQLiteAgentRepository,
)
from personal_agent.memory.candidate import CandidateMemoryService
from personal_agent.memory.conflict import MemoryConflictDetector
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.memory import database

CHINA_TZ = timezone(timedelta(hours=8))
FIXED_NOW = datetime(2026, 7, 23, 14, 0, tzinfo=CHINA_TZ)


class MainCliTests(unittest.TestCase):
    def setUp(self) -> None:
        test_db_uri = f"file:test_main_{uuid4().hex}?mode=memory&cache=shared"
        self.db_patch = patch.object(database, "DB_PATH", test_db_uri)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.anchor = database.connect_db()
        self.addCleanup(self.anchor.close)

        config_path = Path(__file__).resolve().parent / ".test_runtime.json"
        config_path.unlink(missing_ok=True)
        self.addCleanup(config_path.unlink, missing_ok=True)
        self.config_patch = patch.object(
            config_settings,
            "CONFIG_FILE",
            config_path,
        )
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)

        self.clock_patch = patch(
            "personal_agent.interfaces.cli.local_now",
            return_value=FIXED_NOW,
        )
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

        self.repository = SQLiteAgentRepository()
        self.repository.initialize()
        llm = MockLLMClient()
        memory = MemoryManager(self.repository)
        agent = Agent(memory, llm, ContextBuilder(), clock=lambda: FIXED_NOW)
        daily = DailyAnalysisService(
            self.repository,
            DailyMemoryAnalyzer(llm),
            clock=lambda: FIXED_NOW,
        )
        weekly = WeeklyReviewService(self.repository, llm)
        self.scheduler = WorkflowScheduler(
            self.repository,
            daily,
            weekly,
            LocalChannel(),
            clock=lambda: FIXED_NOW,
        )
        self.cli = LocalCLI(
            agent,
            self.repository,
            daily,
            weekly,
            self.scheduler,
            CandidateMemoryService(
                self.repository,
                MemoryConflictDetector(),
                clock=lambda: FIXED_NOW,
            ),
            MemoryLifecycleManager(
                self.repository,
                clock=lambda: FIXED_NOW,
            ),
        )

    def test_cli_lists_goals(self) -> None:
        self.repository.add_goal("学习系统设计")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.cli.handle_command("/goals")
        self.assertIn("学习系统设计", buffer.getvalue())

    def test_task_add_complete_and_reopen(self) -> None:
        goal_id = self.repository.add_goal("产品开发")
        self.cli.handle_command(f"/task-add {goal_id} 完成原型")
        week_start = FIXED_NOW.date() - timedelta(days=FIXED_NOW.weekday())
        tasks = self.repository.tasks_for_week(week_start)
        self.assertEqual(len(tasks), 1)
        task_id = int(tasks[0]["id"])

        self.cli.handle_command(f"/task-done {task_id}")
        self.assertTrue(self.repository.tasks_for_week(week_start)[0]["completed"])
        self.cli.handle_command(f"/task-reopen {task_id}")
        self.assertFalse(self.repository.tasks_for_week(week_start)[0]["completed"])

    def test_settings_reconfigure_scheduler(self) -> None:
        self.addCleanup(schedule.clear)
        self.cli.handle_command("/settings 9")
        self.assertEqual(self.repository.settings()["reminder_hour"], 9)
        jobs = schedule.get_jobs("local_assistant")
        self.assertTrue(
            any(
                job.at_time is not None
                and job.at_time.strftime("%H:%M") == "09:00"
                for job in jobs
            )
        )

    def test_scheduler_contains_analysis_and_retry(self) -> None:
        self.addCleanup(schedule.clear)
        self.scheduler.configure(20)
        jobs = schedule.get_jobs("local_assistant")
        self.assertEqual(len(jobs), 4)
        self.assertTrue(
            any(
                job.at_time is not None
                and job.at_time.strftime("%H:%M") == "00:05"
                for job in jobs
            )
        )
        self.assertTrue(
            any(job.interval == 30 and job.unit == "minutes" for job in jobs)
        )

    def test_scheduler_registers_fixed_daily_backup_when_configured(self) -> None:
        self.addCleanup(schedule.clear)
        calls: list[str] = []
        self.scheduler.backup_database = lambda: calls.append("backup")

        self.scheduler.configure(20)

        jobs = schedule.get_jobs("local_assistant")
        backup_job = next(
            job
            for job in jobs
            if job.at_time is not None
            and job.at_time.strftime("%H:%M") == "00:30"
        )
        backup_job.run()
        self.assertEqual(calls, ["backup"])

    def test_memory_candidate_can_be_reviewed_and_accepted_from_cli(self) -> None:
        analysis_date = FIXED_NOW.date() - timedelta(days=1)
        session_id = self.repository.get_or_create_session(
            analysis_date,
            FIXED_NOW.isoformat(),
        )
        self.repository.add_message(
            session_id,
            "user",
            "我正在开发个人 Agent 项目。",
            FIXED_NOW.isoformat(),
        )
        self.repository.save_analysis_and_purge(
            analysis_date,
            {
                "summary": "用户推进个人 Agent 项目。",
                "progress": ["明确了项目方向"],
                "obstacles": [],
                "patterns": [],
                "mood": "稳定",
                "next_actions": [],
            },
            "test-model",
            1,
            FIXED_NOW.isoformat(),
            [
                {
                    "type": "project",
                    "content": "用户正在开发个人 Agent 项目",
                    "importance": 0.8,
                    "confidence": 0.75,
                }
            ],
        )
        candidate_id = int(self.repository.candidates()[0]["id"])

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.cli.handle_command("/memory candidates")
            self.cli.handle_command(f"/memory accept {candidate_id}")
            self.cli.handle_command("/memory list")
            memory_id = int(self.repository.memories()[0]["id"])
            self.cli.handle_command(f"/memory show {memory_id}")

        output = buffer.getvalue()
        self.assertIn("待审核候选记忆", output)
        self.assertIn("已保存为正式记忆", output)
        self.assertIn("用户正在开发个人 Agent 项目", output)
        self.assertIn("来源：daily_report", output)
        self.assertEqual(self.repository.candidates(), [])


if __name__ == "__main__":
    unittest.main()
