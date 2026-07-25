from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from personal_agent.memory import database


class AgentRepository(Protocol):
    """Persistence boundary consumed by core and analysis services."""

    def initialize(self) -> None: ...

    def add_goal(self, title: str) -> int: ...

    def active_goals(self) -> list[dict[str, object]]: ...

    def add_task(self, goal_id: int, description: str, week_start: date) -> int: ...

    def add_personal_task(
        self,
        description: str,
        week_start: date,
        scope: str = "week",
        task_date: date | None = None,
    ) -> int: ...

    def tasks_for_week(self, week_start: date) -> list[dict[str, object]]: ...

    def set_task_completed(self, task_id: int, completed: bool) -> bool: ...

    def settings(self) -> dict[str, object | None]: ...

    def save_settings(
        self,
        reminder_hour: int | None = None,
        setup_complete: bool | None = None,
    ) -> None: ...

    def log_error(self, task_name: str, error_msg: str) -> None: ...

    def get_or_create_session(self, session_date: date, started_at: str) -> int: ...

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        created_at: str,
        goal_id: int | None = None,
        task_id: int | None = None,
    ) -> int: ...

    def messages_for_date(self, session_date: date) -> list[dict[str, object]]: ...

    def pending_chat_dates(self, before_date: date) -> list[date]: ...

    def mark_session_failed(self, session_date: date, error_message: str) -> None: ...

    def save_analysis_and_purge(
        self,
        analysis_date: date,
        analysis: dict[str, Any],
        model_name: str,
        message_count: int,
        created_at: str,
        memory_candidates: list[dict[str, object]] | None = None,
        evidence: list[dict[str, object]] | None = None,
    ) -> None: ...

    def daily_analysis(self, analysis_date: date) -> dict[str, object] | None: ...

    def report_evidence(
        self,
        analysis_date: date,
    ) -> list[dict[str, object]]: ...

    def recent_analyses(
        self,
        before_date: date,
        limit: int = 7,
    ) -> list[dict[str, object]]: ...

    def analyses_between(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]: ...

    def memories(
        self,
        status: str = "active",
        memory_types: list[str] | None = None,
    ) -> list[dict[str, object]]: ...

    def search_memories(
        self,
        keywords: list[str],
        memory_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]: ...

    def mark_memories_used(self, memory_ids: list[int], used_at: str) -> None: ...

    def candidates(self, status: str = "pending") -> list[dict[str, object]]: ...

    def candidate(self, candidate_id: int) -> dict[str, object] | None: ...

    def update_candidate(
        self,
        candidate_id: int,
        memory_type: str,
        content: str,
        importance: float,
        confidence: float,
    ) -> bool: ...

    def reject_candidate(self, candidate_id: int, reviewed_at: str) -> bool: ...

    def accept_candidate(self, candidate_id: int, reviewed_at: str) -> int: ...

    def set_memory_status(
        self,
        memory_id: int,
        status: str,
        updated_at: str,
    ) -> bool: ...

    def memory_provenance(
        self,
        memory_id: int,
    ) -> list[dict[str, object]]: ...


class SQLiteAgentRepository:
    """SQLite implementation of the persistence boundary."""

    def initialize(self) -> None:
        database.init_db()

    def add_goal(self, title: str) -> int:
        return database.add_goal(title)

    def active_goals(self) -> list[dict[str, object]]:
        return database.get_active_goals()

    def add_task(self, goal_id: int, description: str, week_start: date) -> int:
        return database.add_task(goal_id, description, week_start)

    def add_personal_task(
        self,
        description: str,
        week_start: date,
        scope: str = "week",
        task_date: date | None = None,
    ) -> int:
        return database.add_personal_task(
            description,
            week_start,
            scope,
            task_date,
        )

    def tasks_for_week(self, week_start: date) -> list[dict[str, object]]:
        return database.get_all_tasks_for_week(week_start)

    def set_task_completed(self, task_id: int, completed: bool) -> bool:
        return database.set_task_completed(task_id, completed)

    def settings(self) -> dict[str, object | None]:
        return database.get_settings()

    def save_settings(
        self,
        reminder_hour: int | None = None,
        setup_complete: bool | None = None,
    ) -> None:
        database.save_settings(
            reminder_hour=reminder_hour,
            setup_complete=setup_complete,
        )

    def log_error(self, task_name: str, error_msg: str) -> None:
        database.add_error_log(task_name, error_msg)

    def get_or_create_session(self, session_date: date, started_at: str) -> int:
        return database.get_or_create_chat_session(session_date, started_at)

    def add_message(
        self,
        session_id: int,
        role: str,
        content: str,
        created_at: str,
        goal_id: int | None = None,
        task_id: int | None = None,
    ) -> int:
        return database.add_chat_message(
            session_id=session_id,
            role=role,
            content=content,
            created_at=created_at,
            goal_id=goal_id,
            task_id=task_id,
        )

    def messages_for_date(self, session_date: date) -> list[dict[str, object]]:
        return database.get_chat_messages_for_date(session_date)

    def pending_chat_dates(self, before_date: date) -> list[date]:
        return database.list_pending_chat_dates(before_date)

    def mark_session_failed(self, session_date: date, error_message: str) -> None:
        database.mark_chat_session_failed(session_date, error_message)

    def save_analysis_and_purge(
        self,
        analysis_date: date,
        analysis: dict[str, Any],
        model_name: str,
        message_count: int,
        created_at: str,
        memory_candidates: list[dict[str, object]] | None = None,
        evidence: list[dict[str, object]] | None = None,
    ) -> None:
        database.save_daily_analysis_and_delete_chat(
            analysis_date=analysis_date,
            analysis=analysis,
            model_name=model_name,
            message_count=message_count,
            created_at=created_at,
            memory_candidates=memory_candidates,
            evidence=evidence,
        )

    def daily_analysis(self, analysis_date: date) -> dict[str, object] | None:
        return database.get_daily_analysis(analysis_date)

    def report_evidence(
        self,
        analysis_date: date,
    ) -> list[dict[str, object]]:
        return database.get_daily_report_evidence(analysis_date)

    def recent_analyses(
        self,
        before_date: date,
        limit: int = 7,
    ) -> list[dict[str, object]]:
        return database.get_recent_daily_analyses(before_date, limit)

    def analyses_between(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, object]]:
        return database.get_daily_analyses_between(start_date, end_date)

    def memories(
        self,
        status: str = "active",
        memory_types: list[str] | None = None,
    ) -> list[dict[str, object]]:
        return database.list_memories(status, memory_types)

    def search_memories(
        self,
        keywords: list[str],
        memory_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        return database.search_memories(keywords, memory_types, limit)

    def mark_memories_used(self, memory_ids: list[int], used_at: str) -> None:
        database.mark_memories_used(memory_ids, used_at)

    def candidates(self, status: str = "pending") -> list[dict[str, object]]:
        return database.list_candidate_memories(status)

    def candidate(self, candidate_id: int) -> dict[str, object] | None:
        return database.get_candidate_memory(candidate_id)

    def update_candidate(
        self,
        candidate_id: int,
        memory_type: str,
        content: str,
        importance: float,
        confidence: float,
    ) -> bool:
        return database.update_candidate_memory(
            candidate_id,
            memory_type,
            content,
            importance,
            confidence,
        )

    def reject_candidate(self, candidate_id: int, reviewed_at: str) -> bool:
        return database.reject_candidate_memory(candidate_id, reviewed_at)

    def accept_candidate(self, candidate_id: int, reviewed_at: str) -> int:
        return database.accept_candidate_memory(candidate_id, reviewed_at)

    def set_memory_status(
        self,
        memory_id: int,
        status: str,
        updated_at: str,
    ) -> bool:
        return database.set_memory_status(memory_id, status, updated_at)

    def memory_provenance(
        self,
        memory_id: int,
    ) -> list[dict[str, object]]:
        return database.get_memory_provenance(memory_id)
