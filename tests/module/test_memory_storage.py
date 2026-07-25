from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json

import pytest

from personal_agent.analysis import DailyAnalysisService
from personal_agent.memory import DailyMemoryAnalyzer
from personal_agent.memory.candidate import CandidateMemoryService
from personal_agent.memory.conflict import MemoryConflictDetector
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.memory.retriever import MemoryRetriever

NOW = datetime(2026, 7, 24, 8, 0, tzinfo=timezone(timedelta(hours=8)))


class JsonLLM:
    model_name = "json-fixture"

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        assert json_mode
        assert "候选长期记忆" in prompt
        return json.dumps(self.payload, ensure_ascii=False)


def create_candidate(
    repository: object,
    *,
    content: str,
    memory_type: str,
    source_date: date,
) -> int:
    session_id = repository.get_or_create_session(  # type: ignore[attr-defined]
        source_date,
        NOW.isoformat(),
    )
    repository.add_message(  # type: ignore[attr-defined]
        session_id,
        "user",
        content,
        NOW.isoformat(),
    )
    repository.save_analysis_and_purge(  # type: ignore[attr-defined]
        source_date,
        {
            "summary": content,
            "progress": [],
            "obstacles": [],
            "patterns": [],
            "mood": "稳定",
            "next_actions": [],
        },
        "fixture",
        1,
        NOW.isoformat(),
        [
            {
                "type": memory_type,
                "content": content,
                "importance": 0.8,
                "confidence": 0.8,
            }
        ],
    )
    return int(repository.candidates()[0]["id"])  # type: ignore[attr-defined]


@pytest.mark.module
def test_candidate_accept_creates_formal_memory_and_soft_delete(repository) -> None:
    candidate_id = create_candidate(
        repository,
        content="用户喜欢结构化回答",
        memory_type="preference",
        source_date=date(2026, 7, 22),
    )
    service = CandidateMemoryService(
        repository,
        MemoryConflictDetector(),
        clock=lambda: NOW,
    )
    memory_id = service.accept(candidate_id)

    formal = repository.memories("active")
    assert formal[0]["id"] == memory_id
    assert formal[0]["content"] == "用户喜欢结构化回答"
    assert repository.candidates("pending") == []

    lifecycle = MemoryLifecycleManager(repository, clock=lambda: NOW)
    assert lifecycle.delete(memory_id)
    assert repository.memories("active") == []
    deleted = repository.memories("deleted")
    assert deleted[0]["id"] == memory_id


@pytest.mark.module
def test_daily_analyzer_classifies_project_as_pending_candidate(repository) -> None:
    chat_date = date(2026, 7, 23)
    session_id = repository.get_or_create_session(chat_date, NOW.isoformat())
    message_id = repository.add_message(
        session_id,
        "user",
        "用户正在开发个人Agent",
        NOW.isoformat(),
    )
    llm = JsonLLM(
        {
            "summary": "用户推进个人 Agent 项目。",
            "progress": ["完成架构设计"],
            "obstacles": [],
            "patterns": [],
            "mood": "专注",
            "next_actions": ["继续测试"],
            "confidence": 0.9,
            "evidence": [
                {
                    "evidence_type": "progress",
                    "claim": "完成架构设计",
                    "message_id": message_id,
                    "quote": "用户正在开发个人Agent",
                },
                {
                    "evidence_type": "next_action",
                    "claim": "继续测试",
                    "message_id": message_id,
                    "quote": "用户正在开发个人Agent",
                },
            ],
            "memory_candidates": [
                {
                    "type": "project",
                    "content": "用户正在开发个人Agent",
                    "confidence": 0.9,
                    "importance": 0.8,
                    "evidence_message_ids": [message_id],
                    "created_reason": "用户明确说明正在开发个人 Agent",
                }
            ],
        }
    )
    DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(llm),
        clock=lambda: NOW,
    ).analyze_and_purge(chat_date)

    candidates = repository.candidates()
    assert len(candidates) == 1
    assert candidates[0]["type"] == "project"
    assert candidates[0]["status"] == "pending"
    assert repository.memories() == []
    assert repository.messages_for_date(chat_date) == []


@pytest.mark.integration
def test_memory_retrieval_returns_agent_project_not_python_history(repository) -> None:
    service = CandidateMemoryService(
        repository,
        MemoryConflictDetector(),
        clock=lambda: NOW,
    )
    agent_id = create_candidate(
        repository,
        content="用户正在开发个人Agent项目",
        memory_type="project",
        source_date=date(2026, 7, 20),
    )
    service.accept(agent_id)
    python_id = create_candidate(
        repository,
        content="用户正在学习Python基础语法",
        memory_type="skill",
        source_date=date(2026, 7, 21),
    )
    service.accept(python_id)

    memories = MemoryRetriever(
        repository,
        clock=lambda: NOW,
    ).retrieve("我的Agent项目下一步怎么办？")

    contents = [str(item["content"]) for item in memories]
    assert "用户正在开发个人Agent项目" in contents
    assert "用户正在学习Python基础语法" not in contents


@pytest.mark.security
def test_invalid_candidate_type_cannot_enter_storage(repository) -> None:
    chat_date = date(2026, 7, 23)
    session_id = repository.get_or_create_session(chat_date, NOW.isoformat())
    repository.add_message(session_id, "user", "临时信息", NOW.isoformat())
    llm = JsonLLM(
        {
            "summary": "临时信息",
            "progress": [],
            "obstacles": [],
            "patterns": [],
            "mood": "未知",
            "next_actions": [],
            "memory_candidates": [
                {
                    "type": "secret",
                    "content": "不允许的类别",
                }
            ],
        }
    )
    service = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(llm),
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="无效记忆类型"):
        service.analyze_and_purge(chat_date)

    assert len(repository.messages_for_date(chat_date)) == 1
    assert repository.candidates() == []
    assert repository.daily_analysis(chat_date) is None
