from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

from personal_agent.core.clock import local_now
from personal_agent.core.context import ContextBuilder
from personal_agent.core.ports import ConversationMemory
from personal_agent.llm.base import LLMClient


def week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


class Agent:
    """Coordinates one chat turn without knowing SQLite or Ollama details."""

    def __init__(
        self,
        memory: ConversationMemory,
        llm: LLMClient,
        context_builder: ContextBuilder,
        clock: Callable[[], datetime] = local_now,
        tool_runner: object | None = None,
    ) -> None:
        self.memory = memory
        self.llm = llm
        self.context_builder = context_builder
        self.clock = clock
        self.tool_runner = tool_runner

    def chat(self, message: str) -> str:
        cleaned = (message or "").strip()
        if not cleaned:
            raise ValueError("聊天内容不能为空")

        now = self.clock()
        session_id = self.memory.save_user_message(cleaned, now)
        should_handle = getattr(self.tool_runner, "should_handle", None)
        run_tools = getattr(self.tool_runner, "run", None)
        if callable(should_handle) and callable(run_tools) and should_handle(cleaned):
            response = str(run_tools(cleaned).reply).strip()
            self.memory.save_assistant_message(
                session_id=session_id,
                content=response,
                now=self.clock(),
            )
            return response
        context = self.memory.conversation_context(
            today=now.date(),
            week_start=week_start(now.date()),
            query=cleaned,
        )
        prompt = self.context_builder.build_chat_prompt(now.date(), context)
        response = self.llm.complete(prompt).strip()
        if not response:
            raise RuntimeError("模型没有返回有效回复")
        self.memory.save_assistant_message(
            session_id=session_id,
            content=response,
            now=self.clock(),
        )
        return response
