from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from personal_agent.analysis import WeeklyReviewService
from personal_agent.llm.mock import MockLLMClient
from personal_agent.memory import SQLiteAgentRepository
from personal_agent.memory import database


class WeeklyReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        test_db_uri = f"file:test_weekly_{uuid4().hex}?mode=memory&cache=shared"
        self.db_patch = patch.object(
            database,
            "DB_PATH",
            test_db_uri,
        )
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.anchor = database.connect_db()
        self.addCleanup(self.anchor.close)
        self.repository = SQLiteAgentRepository()
        self.repository.initialize()
        self.service = WeeklyReviewService(
            self.repository,
            MockLLMClient(),
        )

    def test_mock_report_marks_missing_information(self) -> None:
        report = self.service.generate(date(2026, 7, 20))
        self.assertIn("信息不足，无法进一步判断", report)
        self.assertIn("0/0", report)

    def test_weekly_report_uses_saved_daily_analyses(self) -> None:
        self.repository.save_analysis_and_purge(
            analysis_date=date(2026, 7, 22),
            analysis={
                "summary": "完成实时聊天功能",
                "progress": ["完成实时聊天功能"],
                "obstacles": ["模型返回格式需要校验"],
                "patterns": [],
                "mood": "专注",
                "next_actions": ["实现凌晨自动分析"],
            },
            model_name="mock",
            message_count=4,
            created_at="2026-07-23T00:05:00+08:00",
        )

        report = self.service.generate(date(2026, 7, 20))

        self.assertIn("完成实时聊天功能", report)
        self.assertNotIn("模型返回格式需要校验", report)
        self.assertIn("值得关注的模式", report)
        self.assertIn("实现凌晨自动分析", report)

    def test_weekly_report_uses_task_completion(self) -> None:
        goal_id = self.repository.add_goal("项目")
        task_id = self.repository.add_task(
            goal_id,
            "完成分层重构",
            date(2026, 7, 20),
        )
        self.repository.set_task_completed(task_id, True)
        report = self.service.generate(date(2026, 7, 20))
        self.assertIn("1/1", report)


if __name__ == "__main__":
    unittest.main()
