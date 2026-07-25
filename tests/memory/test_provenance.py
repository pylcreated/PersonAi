from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json

from personal_agent.analysis import DailyAnalysisService
from personal_agent.memory import DailyMemoryAnalyzer
from personal_agent.memory.candidate import CandidateMemoryService
from personal_agent.memory.conflict import MemoryConflictDetector

CHINA_TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 25, 0, 5, tzinfo=CHINA_TZ)


class ProvenanceLLM:
    model_name = "provenance-fake"

    def __init__(self, message_id: int) -> None:
        self.message_id = message_id

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        return json.dumps(
            {
                "summary": "用户持续开发 Personal Agent。",
                "progress": ["完成数据可靠性模块"],
                "obstacles": [],
                "patterns": [],
                "mood": "专注",
                "next_actions": [],
                "confidence": 0.95,
                "evidence": [
                    {
                        "evidence_type": "progress",
                        "claim": "完成数据可靠性模块",
                        "message_id": self.message_id,
                        "quote": "完成了数据库迁移和备份",
                    }
                ],
                "memory_candidates": [
                    {
                        "type": "project",
                        "content": "用户正在开发 Personal Agent",
                        "confidence": 0.9,
                        "importance": 0.8,
                        "evidence_message_ids": [self.message_id],
                        "created_reason": "用户连续推进同一项目",
                    }
                ],
            },
            ensure_ascii=False,
        )


def test_accepted_memory_keeps_report_reason_and_chat_evidence(repository) -> None:
    chat_date = date(2026, 7, 24)
    session = repository.get_or_create_session(chat_date, NOW.isoformat())
    message_id = repository.add_message(
        session,
        "user",
        "完成了数据库迁移和备份",
        NOW.isoformat(),
    )
    DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(ProvenanceLLM(message_id)),
        clock=lambda: NOW,
    ).analyze_and_purge(chat_date)
    candidate = repository.candidates()[0]

    memory_id = CandidateMemoryService(
        repository,
        MemoryConflictDetector(),
        clock=lambda: NOW,
    ).accept(int(candidate["id"]))

    provenance = repository.memory_provenance(memory_id)
    assert provenance[0]["source_type"] == "daily_report"
    assert provenance[0]["created_reason"] == "用户连续推进同一项目"
    assert provenance[0]["evidence"][0]["message_id"] == message_id
    assert provenance[0]["evidence"][0]["quote"] == "完成了数据库迁移和备份"
    assert repository.messages_for_date(chat_date) == []
