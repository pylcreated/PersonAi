from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json

import pytest

from personal_agent.analysis import DailyAnalysisService
from personal_agent.memory import DailyMemoryAnalyzer, database

CHINA_TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 25, 0, 5, tzinfo=CHINA_TZ)


class EvidenceLLM:
    model_name = "evidence-fake"

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        assert json_mode
        return json.dumps(self.payload, ensure_ascii=False)


def _message(repository, text: str = "FastAPI接口已经测试通过") -> tuple[date, int]:
    chat_date = date(2026, 7, 24)
    session = repository.get_or_create_session(chat_date, NOW.isoformat())
    message_id = repository.add_message(
        session,
        "user",
        text,
        NOW.isoformat(),
    )
    return chat_date, message_id


def _payload(message_id: int, quote: str) -> dict[str, object]:
    return {
        "summary": "用户完成了接口测试。",
        "progress": ["完成FastAPI接口测试"],
        "obstacles": [],
        "patterns": [],
        "mood": "专注",
        "next_actions": ["整理接口文档"],
        "confidence": 0.92,
        "evidence": [
            {
                "evidence_type": "progress",
                "claim": "完成FastAPI接口测试",
                "message_id": message_id,
                "quote": quote,
            },
            {
                "evidence_type": "next_action",
                "claim": "整理接口文档",
                "message_id": message_id,
                "quote": quote,
            },
        ],
        "memory_candidates": [],
    }


def test_daily_report_persists_verified_evidence_and_displays_it(
    repository,
) -> None:
    chat_date, message_id = _message(repository)
    service = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(
            EvidenceLLM(_payload(message_id, "FastAPI接口已经测试通过"))
        ),
        clock=lambda: NOW,
    )

    service.analyze_and_purge(chat_date)

    report = repository.daily_analysis(chat_date)
    assert report is not None
    assert report["confidence"] == pytest.approx(0.92)
    assert report["evidence"][0]["message_id"] == message_id
    assert report["evidence"][0]["quote"] == "FastAPI接口已经测试通过"
    assert repository.messages_for_date(chat_date) == []
    rendered = service.formatted_analysis(chat_date)
    assert rendered is not None
    assert f"消息 #{message_id}" in rendered
    assert "FastAPI接口已经测试通过" in rendered


@pytest.mark.parametrize(
    ("message_id_offset", "quote"),
    [(1000, "FastAPI接口已经测试通过"), (0, "模型编造的原文")],
)
def test_invalid_message_or_quote_keeps_source_chat(
    repository,
    message_id_offset: int,
    quote: str,
) -> None:
    chat_date, message_id = _message(repository)
    service = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(
            EvidenceLLM(_payload(message_id + message_id_offset, quote))
        ),
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError):
        service.analyze_and_purge(chat_date)

    assert repository.daily_analysis(chat_date) is None
    assert len(repository.messages_for_date(chat_date)) == 1


def test_evidence_insert_failure_rolls_back_report_and_chat_cleanup(
    repository,
) -> None:
    chat_date, message_id = _message(repository)
    with database.connect_db() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_test_evidence
            BEFORE INSERT ON daily_report_evidence
            BEGIN
                SELECT RAISE(ABORT, 'evidence failure');
            END
            """
        )
    service = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(
            EvidenceLLM(_payload(message_id, "FastAPI接口已经测试通过"))
        ),
        clock=lambda: NOW,
    )

    with pytest.raises(Exception, match="evidence failure"):
        service.analyze_and_purge(chat_date)

    assert repository.daily_analysis(chat_date) is None
    assert len(repository.messages_for_date(chat_date)) == 1


def test_mock_evidence_only_quotes_real_user_message(repository) -> None:
    chat_date, message_id = _message(repository, "今天完成了本地备份")

    from personal_agent.llm.mock import MockLLMClient

    DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(MockLLMClient()),
        clock=lambda: NOW,
    ).analyze_and_purge(chat_date)

    evidence = repository.report_evidence(chat_date)
    assert len(evidence) == 1
    assert evidence[0]["message_id"] == message_id
    assert evidence[0]["quote"] == "今天完成了本地备份"


def test_daily_analysis_accepts_missing_or_string_obstacles(repository) -> None:
    chat_date, message_id = _message(repository)
    payload = _payload(message_id, "FastAPI接口已经测试通过")
    payload["obstacles"] = "旧模型返回的字符串格式"
    service = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(EvidenceLLM(payload)),
        clock=lambda: NOW,
    )

    service.analyze_and_purge(chat_date)

    report = repository.daily_analysis(chat_date)
    assert report is not None
    assert report["obstacles"] == []
