from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from personal_agent.analysis import DailyAnalysisService
from personal_agent.core import Agent, ContextBuilder
from personal_agent.llm.mock import MockLLMClient
from personal_agent.memory import (
    DailyMemoryAnalyzer,
    MemoryManager,
    SQLiteAgentRepository,
)
from personal_agent.memory import database

CHINA_TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 23, 14, 30, tzinfo=CHINA_TZ)


class FakeLLM:
    def __init__(self, response: str, model_name: str = "fake") -> None:
        self.response = response
        self._model_name = model_name
        self.calls: list[tuple[str, bool]] = []

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((prompt, json_mode))
        return self.response


class ConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        test_db_uri = f"file:test_conversation_{uuid4().hex}?mode=memory&cache=shared"
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

    def _add_chat(self, chat_date: date) -> None:
        session_id = self.repository.get_or_create_session(
            chat_date,
            f"{chat_date.isoformat()}T10:00:00+08:00",
        )
        self.repository.add_message(
            session_id,
            "user",
            "今天完成了数据库设计",
            f"{chat_date.isoformat()}T10:00:00+08:00",
        )
        self.repository.add_message(
            session_id,
            "assistant",
            "已经记录，可以继续实现。",
            f"{chat_date.isoformat()}T10:01:00+08:00",
        )

    def test_agent_coordinates_memory_context_and_llm(self) -> None:
        llm = FakeLLM("这是模型回复")
        agent = Agent(
            MemoryManager(self.repository),
            llm,
            ContextBuilder(),
            clock=lambda: NOW,
        )
        reply = agent.chat("今天开始实现分层架构")

        messages = self.repository.messages_for_date(NOW.date())
        self.assertEqual(reply, "这是模型回复")
        self.assertEqual([item["role"] for item in messages], ["user", "assistant"])
        self.assertIn("今天开始实现分层架构", llm.calls[0][0])

    def test_successful_analysis_saves_summary_and_deletes_raw_chat(self) -> None:
        chat_date = date(2026, 7, 22)
        self._add_chat(chat_date)
        service = DailyAnalysisService(
            self.repository,
            DailyMemoryAnalyzer(MockLLMClient()),
            clock=lambda: NOW,
        )

        result = service.analyze_and_purge(chat_date)

        self.assertIsNotNone(result)
        self.assertEqual(self.repository.messages_for_date(chat_date), [])
        saved = self.repository.daily_analysis(chat_date)
        self.assertEqual(saved["message_count"], 2)
        self.assertIn("今天完成了数据库设计", saved["summary"])

    def test_invalid_analysis_keeps_raw_chat_for_retry(self) -> None:
        chat_date = date(2026, 7, 22)
        self._add_chat(chat_date)
        service = DailyAnalysisService(
            self.repository,
            DailyMemoryAnalyzer(FakeLLM("不是有效 JSON")),
            clock=lambda: NOW,
        )

        with self.assertRaises(ValueError):
            service.analyze_and_purge(chat_date)

        self.assertEqual(len(self.repository.messages_for_date(chat_date)), 2)
        self.assertIsNone(self.repository.daily_analysis(chat_date))
        with database.connect_db() as conn:
            status = conn.execute(
                "SELECT status FROM chat_sessions WHERE session_date = ?",
                (chat_date.isoformat(),),
            ).fetchone()[0]
        self.assertEqual(status, "failed")

    def test_daily_analysis_requests_json_mode(self) -> None:
        chat_date = date(2026, 7, 22)
        self._add_chat(chat_date)
        valid_json = (
            '{"summary":"完成设计","progress":[],"obstacles":[],'
            '"patterns":[],"mood":"专注","next_actions":[]}'
        )
        llm = FakeLLM(valid_json)
        service = DailyAnalysisService(
            self.repository,
            DailyMemoryAnalyzer(llm),
            clock=lambda: NOW,
        )

        service.analyze_and_purge(chat_date)

        self.assertTrue(llm.calls[0][1])

    def test_startup_catchup_only_processes_previous_days(self) -> None:
        yesterday = date(2026, 7, 22)
        today = date(2026, 7, 23)
        self._add_chat(yesterday)
        self._add_chat(today)
        service = DailyAnalysisService(
            self.repository,
            DailyMemoryAnalyzer(MockLLMClient()),
            clock=lambda: NOW,
        )

        completed = service.process_pending(today=today)

        self.assertEqual(completed, [yesterday])
        self.assertEqual(self.repository.messages_for_date(yesterday), [])
        self.assertEqual(len(self.repository.messages_for_date(today)), 2)


if __name__ == "__main__":
    unittest.main()
