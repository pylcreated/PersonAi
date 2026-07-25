from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from personal_agent.analysis import DailyAnalysisService
from personal_agent.core import Agent, ContextBuilder
from personal_agent.memory import (
    DailyMemoryAnalyzer,
    MemoryManager,
    SQLiteAgentRepository,
)
from personal_agent.memory import database
from personal_agent.memory.candidate import (
    CandidateMemoryService,
    MemoryConflictError,
)
from personal_agent.memory.conflict import MemoryConflictDetector
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.memory.retriever import MemoryRetriever

CHINA_TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 24, 0, 5, tzinfo=CHINA_TZ)


class FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[str, bool]] = []

    @property
    def model_name(self) -> str:
        return "fake"

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((prompt, json_mode))
        return self.response


class MemorySystemTests(unittest.TestCase):
    def setUp(self) -> None:
        uri = f"file:test_memory_{uuid4().hex}?mode=memory&cache=shared"
        self.db_patch = patch.object(database, "DB_PATH", uri)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.anchor = database.connect_db()
        self.addCleanup(self.anchor.close)
        self.repository = SQLiteAgentRepository()
        self.repository.initialize()
        self.candidates = CandidateMemoryService(
            self.repository,
            MemoryConflictDetector(),
            clock=lambda: NOW,
        )
        self.lifecycle = MemoryLifecycleManager(
            self.repository,
            clock=lambda: NOW,
        )

    @staticmethod
    def _analysis() -> dict[str, object]:
        return {
            "summary": "当日总结",
            "progress": [],
            "obstacles": [],
            "patterns": [],
            "mood": "专注",
            "next_actions": [],
        }

    def _insert_candidate(
        self,
        *,
        content: str,
        memory_type: str = "project",
        source_date: date = date(2026, 7, 23),
    ) -> int:
        self.repository.save_analysis_and_purge(
            analysis_date=source_date,
            analysis=self._analysis(),
            model_name="fake",
            message_count=2,
            created_at=NOW.isoformat(),
            memory_candidates=[
                {
                    "type": memory_type,
                    "content": content,
                    "importance": 0.7,
                    "confidence": 0.8,
                }
            ],
        )
        return int(self.candidates.pending()[-1]["id"])

    def test_daily_analysis_creates_candidate_before_raw_chat_is_deleted(self) -> None:
        chat_date = date(2026, 7, 23)
        session_id = self.repository.get_or_create_session(
            chat_date,
            "2026-07-23T10:00:00+08:00",
        )
        self.repository.add_message(
            session_id,
            "user",
            "我正在开发一个个人Agent项目",
            "2026-07-23T10:00:00+08:00",
        )
        response = """
        {
          "summary": "用户讨论个人Agent",
          "progress": [],
          "obstacles": [],
          "patterns": [],
          "mood": "专注",
          "next_actions": [],
          "memory_candidates": [
            {
              "type": "project",
              "content": "用户正在开发个人Agent",
              "confidence": 0.8,
              "importance": 0.7
            }
          ]
        }
        """
        service = DailyAnalysisService(
            self.repository,
            DailyMemoryAnalyzer(FakeLLM(response)),
            clock=lambda: NOW,
        )

        service.analyze_and_purge(chat_date)

        self.assertEqual(self.repository.messages_for_date(chat_date), [])
        pending = self.candidates.pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["content"], "用户正在开发个人Agent")
        self.assertEqual(self.lifecycle.list(), [])

    def test_accept_promotes_candidate_with_user_confirmed_confidence(self) -> None:
        candidate_id = self._insert_candidate(content="用户正在开发个人Agent")

        memory_id = self.candidates.accept(candidate_id)

        memories = self.lifecycle.list()
        self.assertEqual(memories[0]["id"], memory_id)
        self.assertEqual(memories[0]["confidence"], 0.9)
        self.assertEqual(self.candidates.pending(), [])

    def test_edit_and_reject_keep_candidate_out_of_formal_memory(self) -> None:
        candidate_id = self._insert_candidate(content="用户可能喜欢长回答")
        self.assertTrue(
            self.candidates.edit(
                candidate_id,
                memory_type="preference",
                content="用户喜欢结构化拆解",
            )
        )
        edited = self.repository.candidate(candidate_id)
        self.assertEqual(edited["type"], "preference")
        self.assertEqual(edited["content"], "用户喜欢结构化拆解")

        self.assertTrue(self.candidates.reject(candidate_id))
        self.assertEqual(self.candidates.pending(), [])
        self.assertEqual(self.lifecycle.list(), [])

    def test_conflict_requires_explicit_force(self) -> None:
        first = self._insert_candidate(
            content="用户准备考研",
            memory_type="goal",
            source_date=date(2026, 7, 21),
        )
        self.candidates.accept(first)
        second = self._insert_candidate(
            content="用户准备就业",
            memory_type="goal",
            source_date=date(2026, 7, 22),
        )

        with self.assertRaises(MemoryConflictError):
            self.candidates.accept(second)
        self.assertEqual(len(self.lifecycle.list()), 1)

        self.candidates.accept(second, force=True)
        self.assertEqual(len(self.lifecycle.list()), 2)

    def test_only_confirmed_relevant_memory_is_injected_into_context(self) -> None:
        accepted = self._insert_candidate(
            content="用户正在开发个人Agent",
            memory_type="project",
        )
        self.candidates.accept(accepted)
        self._insert_candidate(
            content="用户可能计划学习摄影",
            memory_type="goal",
            source_date=date(2026, 7, 22),
        )
        llm = FakeLLM("继续完善分层结构")
        memory = MemoryManager(
            self.repository,
            MemoryRetriever(self.repository, clock=lambda: NOW),
        )
        agent = Agent(
            memory,
            llm,
            ContextBuilder(),
            clock=lambda: NOW,
        )

        agent.chat("我的Agent项目下一步怎么办？")

        prompt = llm.calls[0][0]
        self.assertIn("用户正在开发个人Agent", prompt)
        self.assertNotIn("用户可能计划学习摄影", prompt)

    def test_general_question_skips_personal_memory(self) -> None:
        accepted = self._insert_candidate(
            content="用户正在开发个人Agent",
            memory_type="project",
        )
        self.candidates.accept(accepted)
        retriever = MemoryRetriever(self.repository, clock=lambda: NOW)
        self.assertEqual(retriever.retrieve("Transformer是什么？"), [])

    def test_deleted_memory_is_not_retrieved(self) -> None:
        accepted = self._insert_candidate(
            content="用户正在开发个人Agent",
            memory_type="project",
        )
        memory_id = self.candidates.accept(accepted)
        self.assertTrue(self.lifecycle.delete(memory_id))
        retriever = MemoryRetriever(self.repository, clock=lambda: NOW)
        self.assertEqual(retriever.retrieve("我的Agent项目怎么样？"), [])


if __name__ == "__main__":
    unittest.main()
