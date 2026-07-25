from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json

import pytest

from personal_agent.agent import (
    AgentOrchestrator,
    Executor,
    Planner,
    PlanningContextProvider,
    ReviewDecision,
    RiskAnalyzer,
)
from personal_agent.analysis import DailyAnalysisService
from personal_agent.core import Agent, ContextBuilder
from personal_agent.memory import DailyMemoryAnalyzer, MemoryManager
from personal_agent.memory.candidate import CandidateMemoryService
from personal_agent.memory.conflict import MemoryConflictDetector
from personal_agent.memory.retriever import MemoryRetriever

NOW = datetime(2026, 7, 24, 9, 0, tzinfo=timezone(timedelta(hours=8)))


class PayloadLLM:
    model_name = "scenario"

    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        self.prompts.append(prompt)
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload, ensure_ascii=False)


class Approve:
    def review(self, plan) -> ReviewDecision:
        del plan
        return ReviewDecision(True)


def add_candidate(
    repository,
    source_date: date,
    memory_type: str,
    content: str,
) -> int:
    session = repository.get_or_create_session(source_date, NOW.isoformat())
    repository.add_message(session, "user", content, NOW.isoformat())
    repository.save_analysis_and_purge(
        source_date,
        {
            "summary": content,
            "progress": [],
            "obstacles": [],
            "patterns": [],
            "mood": "稳定",
            "next_actions": [],
        },
        "scenario",
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
    return int(repository.candidates()[0]["id"])


@pytest.mark.scenario
def test_learning_day_chat_to_summary_file_and_memory_candidate(
    repository,
    tool_sandbox,
) -> None:
    chat_date = date(2026, 7, 23)
    session = repository.get_or_create_session(chat_date, NOW.isoformat())
    message_id = repository.add_message(
        session,
        "user",
        "今天学习了 pytest fixture 和权限测试。",
        NOW.isoformat(),
    )
    analysis_llm = PayloadLLM(
        {
            "summary": "用户学习了 pytest fixture 和权限测试。",
            "progress": ["完成测试体系学习"],
            "obstacles": [],
            "patterns": ["倾向于分层验证"],
            "mood": "专注",
            "next_actions": ["整理测试笔记"],
            "confidence": 0.9,
            "evidence": [
                {
                    "evidence_type": "progress",
                    "claim": "完成测试体系学习",
                    "message_id": message_id,
                    "quote": "今天学习了 pytest fixture 和权限测试。",
                },
                {
                    "evidence_type": "pattern",
                    "claim": "倾向于分层验证",
                    "message_id": message_id,
                    "quote": "今天学习了 pytest fixture 和权限测试。",
                },
                {
                    "evidence_type": "next_action",
                    "claim": "整理测试笔记",
                    "message_id": message_id,
                    "quote": "今天学习了 pytest fixture 和权限测试。",
                },
            ],
            "memory_candidates": [
                {
                    "type": "skill",
                    "content": "用户正在学习 pytest 测试体系",
                    "confidence": 0.8,
                    "importance": 0.7,
                    "evidence_message_ids": [message_id],
                    "created_reason": "用户明确记录了持续学习内容",
                }
            ],
        }
    )
    analysis = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(analysis_llm),
        clock=lambda: NOW,
    ).analyze_and_purge(chat_date)
    assert analysis is not None
    assert repository.messages_for_date(chat_date) == []
    assert repository.candidates()[0]["status"] == "pending"

    output = tool_sandbox.workspace / "学习总结.md"
    planner_llm = PayloadLLM(
        {
            "goal": "保存学习总结",
            "steps": [
                {
                    "tool": "create_file",
                    "description": "生成 Markdown 学习总结",
                    "arguments": {
                        "path": str(output),
                        "content": (
                            "# 今日学习总结\n\n"
                            "学习了 pytest fixture 和权限测试。"
                        ),
                    },
                }
            ],
        }
    )
    memory = MemoryManager(repository, MemoryRetriever(repository))
    orchestrator = AgentOrchestrator(
        Planner(
            planner_llm,
            tool_sandbox.registry,
            PlanningContextProvider(memory, clock=lambda: NOW),
        ),
        RiskAnalyzer(),
        Approve(),
        Executor(tool_sandbox.manager),
        tool_sandbox.task_state,
        clock=lambda: NOW,
    )
    result = orchestrator.run("帮我整理今天学习内容并保存")

    assert result.status == "completed"
    assert output.is_file()
    assert "pytest fixture" in output.read_text(encoding="utf-8")
    assert "最近每日摘要" in planner_llm.prompts[0]
    assert "用户学习了 pytest fixture 和权限测试" in planner_llm.prompts[0]


@pytest.mark.scenario
def test_project_status_question_uses_only_relevant_confirmed_memory(
    repository,
) -> None:
    candidate_service = CandidateMemoryService(
        repository,
        MemoryConflictDetector(),
        clock=lambda: NOW,
    )
    project_id = add_candidate(
        repository,
        date(2026, 7, 20),
        "project",
        "用户正在开发个人Agent项目",
    )
    candidate_service.accept(project_id)
    python_id = add_candidate(
        repository,
        date(2026, 7, 21),
        "skill",
        "用户正在学习Python基础语法",
    )
    candidate_service.accept(python_id)

    chat_llm = PayloadLLM("你的个人Agent项目正在推进测试体系。")
    agent = Agent(
        MemoryManager(repository, MemoryRetriever(repository, clock=lambda: NOW)),
        chat_llm,
        ContextBuilder(),
        clock=lambda: NOW,
    )
    response = agent.chat("我的Agent项目现在怎么样？")

    assert "测试体系" in response
    prompt = chat_llm.prompts[0]
    memory_section = prompt.split(
        "用户确认的相关长期记忆：",
        maxsplit=1,
    )[1].split("今天截至目前的对话：", maxsplit=1)[0]
    assert "用户正在开发个人Agent项目" in memory_section
    assert "用户正在学习Python基础语法" not in memory_section
