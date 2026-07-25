from __future__ import annotations

from datetime import date, datetime

from personal_agent.core.context import ConversationContext
from personal_agent.memory.repository import AgentRepository
from personal_agent.memory.retriever import MemoryRetriever


class MemoryManager:
    """Provider-neutral memory API used by the agent core."""

    def __init__(
        self,
        repository: AgentRepository,
        retriever: MemoryRetriever | None = None,
    ) -> None:
        self.repository = repository
        self.retriever = retriever

    def save_user_message(self, content: str, now: datetime) -> int:
        session_id = self.repository.get_or_create_session(
            now.date(),
            now.isoformat(),
        )
        self.repository.add_message(
            session_id=session_id,
            role="user",
            content=content,
            created_at=now.isoformat(),
        )
        return session_id

    def save_assistant_message(
        self,
        session_id: int,
        content: str,
        now: datetime,
    ) -> None:
        self.repository.add_message(
            session_id=session_id,
            role="assistant",
            content=content,
            created_at=now.isoformat(),
        )

    def conversation_context(
        self,
        today: date,
        week_start: date,
        query: str,
        analysis_limit: int = 7,
    ) -> ConversationContext:
        return ConversationContext(
            goals=self.repository.active_goals(),
            tasks=self.repository.tasks_for_week(week_start),
            messages=self.repository.messages_for_date(today),
            recent_analyses=self.repository.recent_analyses(
                today,
                limit=analysis_limit,
            ),
            memories=(
                self.retriever.retrieve(query)
                if self.retriever is not None
                else []
            ),
        )
