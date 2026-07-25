from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from personal_agent.core.context import ConversationContext


class ConversationMemory(Protocol):
    """Memory boundary required by the core Agent."""

    def save_user_message(self, content: str, now: datetime) -> int: ...

    def save_assistant_message(
        self,
        session_id: int,
        content: str,
        now: datetime,
    ) -> None: ...

    def conversation_context(
        self,
        today: date,
        week_start: date,
        query: str,
        analysis_limit: int = 7,
    ) -> ConversationContext: ...
