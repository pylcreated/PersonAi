from __future__ import annotations

import sqlite3
import json
from datetime import UTC, date, datetime
from pathlib import Path
import re
from typing import Any, Optional

from personal_agent.memory.migrations import MigrationManager

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH: str | Path = (
    PROJECT_ROOT / "data" / "database" / "goals_assistant.db"
)


class ClosingConnection(sqlite3.Connection):
    """Commit or roll back on context exit, then always release the file handle."""

    def __exit__(self, *args: object) -> bool:
        try:
            return bool(super().__exit__(*args))
        finally:
            self.close()


def connect_db() -> sqlite3.Connection:
    """Open the configured database, including shared-memory test URIs."""
    target = str(DB_PATH)
    if not target.startswith("file:"):
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        target,
        uri=target.startswith("file:"),
        factory=ClosingConnection,
    )
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Upgrade the SQLite schema and ensure baseline compatibility defaults."""
    MigrationManager(connect_db).migrate()
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                week_start TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(goal_id) REFERENCES goals(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                goal_id INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                user_answer TEXT NOT NULL,
                ai_summary TEXT,
                FOREIGN KEY(goal_id) REFERENCES goals(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                reminder_hour INTEGER,
                setup_complete INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task_name TEXT NOT NULL,
                error_msg TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                closed_at TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                last_error TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                goal_id INTEGER,
                task_id INTEGER,
                FOREIGN KEY(session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY(goal_id) REFERENCES goals(id),
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_date TEXT NOT NULL UNIQUE,
                summary TEXT NOT NULL,
                progress TEXT NOT NULL,
                obstacles TEXT NOT NULL,
                patterns TEXT NOT NULL,
                mood TEXT NOT NULL,
                next_actions TEXT NOT NULL,
                model_name TEXT NOT NULL,
                message_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 0.5
                    CHECK (importance BETWEEN 0 AND 1),
                confidence REAL NOT NULL DEFAULT 0.5
                    CHECK (confidence BETWEEN 0 AND 1),
                source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'expired', 'archived', 'deleted')),
                use_count INTEGER NOT NULL DEFAULT 0,
                last_used_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                type TEXT NOT NULL,
                importance REAL NOT NULL DEFAULT 0.5
                    CHECK (importance BETWEEN 0 AND 1),
                confidence REAL NOT NULL DEFAULT 0.5
                    CHECK (confidence BETWEEN 0 AND 1),
                source_conversation INTEGER,
                source_date TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'accepted', 'rejected')),
                created_at TEXT NOT NULL,
                reviewed_at TEXT
            )
            """
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reflections_goal_timestamp ON reflections(goal_id, timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_week_goal ON tasks(week_start, goal_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_status_type ON memories(status, type)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidate_status ON candidate_memories(status, id)"
        )

        cursor.execute("SELECT 1 FROM settings WHERE id = 1")
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO settings (id, reminder_hour, setup_complete) VALUES (1, NULL, 0)"
            )

        conn.commit()


def add_goal(title: str) -> int:
    """Create a new goal and return its generated id."""
    # sanitize title: remove control characters, collapse whitespace, strip
    if title is None:
        raise ValueError("title must be provided")
    # Replace CR/LF and other control chars with space
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", title)
    # remove leading/trailing whitespace and collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("goal title is empty after sanitization")

    created_at = datetime.now(UTC).isoformat()
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO goals (title, created_at, active) VALUES (?, ?, 1)",
            (cleaned, created_at),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_active_goals() -> list[dict[str, object]]:
    """Return all currently active goals."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT id, title, created_at, active FROM goals WHERE active = 1 ORDER BY created_at DESC"
        ).fetchall()

    return [dict(row) for row in rows]


def add_task(goal_id: int, description: str, week_start: date) -> int:
    """Create a task under a goal for a specific week."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", description or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("task description is empty")

    with connect_db() as conn:
        cursor = conn.cursor()
        goal = cursor.execute(
            "SELECT 1 FROM goals WHERE id = ? AND active = 1",
            (goal_id,),
        ).fetchone()
        if goal is None:
            raise ValueError("active goal not found")
        cursor.execute(
            "INSERT INTO tasks (goal_id, description, week_start, completed) VALUES (?, ?, ?, 0)",
            (goal_id, cleaned, week_start.isoformat()),
        )
        conn.commit()
        return int(cursor.lastrowid)


def add_personal_task(
    description: str,
    week_start: date,
    scope: str = "week",
    task_date: date | None = None,
) -> int:
    """Create an independent daily or weekly checklist task."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", description or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("task description is empty")
    if scope not in {"day", "week"}:
        raise ValueError("task scope must be day or week")
    effective_date = task_date or date.today()
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO personal_tasks (
                description, scope, task_date, week_start, completed, created_at
            )
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (
                cleaned,
                scope,
                effective_date.isoformat() if scope == "day" else None,
                week_start.isoformat(),
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()
        return -int(cursor.lastrowid)


def get_tasks_for_week(goal_id: int, week_start: date) -> list[dict[str, object]]:
    """Return tasks for a specific goal and week."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT id, goal_id, description, week_start, completed FROM tasks WHERE goal_id = ? AND week_start = ? ORDER BY id ASC",
            (goal_id, week_start.isoformat()),
        ).fetchall()

    return [dict(row) for row in rows]


def get_all_tasks_for_week(week_start: date) -> list[dict[str, object]]:
    """Return all tasks for a week together with their goal titles."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        legacy_rows = conn.execute(
            """
            SELECT t.id, t.goal_id, t.description, t.week_start, t.completed, g.title AS goal_title
            FROM tasks AS t
            JOIN goals AS g ON g.id = t.goal_id
            WHERE t.week_start = ?
            ORDER BY t.completed ASC, t.id ASC
            """,
            (week_start.isoformat(),),
        ).fetchall()
        personal_rows = conn.execute(
            """
            SELECT -id AS id, NULL AS goal_id, description, week_start,
                   completed, '任务清单' AS goal_title, scope, task_date
            FROM personal_tasks
            WHERE week_start = ?
            ORDER BY completed ASC, id ASC
            """,
            (week_start.isoformat(),),
        ).fetchall()

    legacy = [
        {
            **dict(row),
            "scope": "week",
            "task_date": None,
        }
        for row in legacy_rows
    ]
    personal = [dict(row) for row in personal_rows]
    return sorted(
        legacy + personal,
        key=lambda item: (int(item["completed"]), abs(int(item["id"]))),
    )


def set_task_completed(task_id: int, completed: bool = True) -> bool:
    """Set a task's completion state and report whether it existed."""
    with connect_db() as conn:
        if task_id < 0:
            cursor = conn.execute(
                "UPDATE personal_tasks SET completed = ? WHERE id = ?",
                (1 if completed else 0, abs(task_id)),
            )
        else:
            cursor = conn.execute(
                "UPDATE tasks SET completed = ? WHERE id = ?",
                (1 if completed else 0, task_id),
            )
        conn.commit()
        return cursor.rowcount > 0


def add_reflection(
    goal_id: int,
    question_type: str,
    user_answer: str,
    ai_summary: Optional[str] = None,
) -> int:
    """Save a reflection entry for a goal."""
    timestamp = datetime.now(UTC).isoformat()
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reflections (timestamp, goal_id, question_type, user_answer, ai_summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (timestamp, goal_id, question_type, user_answer, ai_summary),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_reflections_between_dates(
    goal_id: int,
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    """Return reflections for a goal within a date range inclusive."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT id, timestamp, goal_id, question_type, user_answer, ai_summary
            FROM reflections
            WHERE goal_id = ? AND date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp ASC
            """,
            (goal_id, start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    return [dict(row) for row in rows]


def get_settings() -> dict[str, Optional[object]]:
    """Read the persisted onboarding settings row."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT reminder_hour, setup_complete FROM settings WHERE id = 1"
        ).fetchone()

    if row is None:
        return {"reminder_hour": None, "setup_complete": False}

    return {
        "reminder_hour": int(row["reminder_hour"]) if row["reminder_hour"] is not None else None,
        "setup_complete": bool(row["setup_complete"]),
    }


def save_settings(reminder_hour: Optional[int] = None, setup_complete: Optional[bool] = None) -> None:
    """Update reminder hour and setup completion state in the settings table."""
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM settings WHERE id = 1")
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO settings (id, reminder_hour, setup_complete) VALUES (1, ?, ?)",
                (reminder_hour, int(setup_complete is True) if setup_complete is not None else 0),
            )
        else:
            updates: list[str] = []
            values: list[object] = []
            if reminder_hour is not None:
                updates.append("reminder_hour = ?")
                values.append(reminder_hour)
            if setup_complete is not None:
                updates.append("setup_complete = ?")
                values.append(1 if setup_complete else 0)
            if updates:
                cursor.execute(
                    f"UPDATE settings SET {', '.join(updates)} WHERE id = 1",
                    values,
                )
        conn.commit()


def add_error_log(task_name: str, error_msg: str) -> None:
    """Persist a task failure message for later inspection."""
    timestamp = datetime.now(UTC).isoformat()
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO error_log (timestamp, task_name, error_msg) VALUES (?, ?, ?)",
            (timestamp, task_name, error_msg),
        )
        conn.commit()


def get_or_create_chat_session(session_date: date, started_at: str) -> int:
    """Return the daily chat session, creating it when necessary."""
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_sessions (session_date, started_at, status)
            VALUES (?, ?, 'active')
            ON CONFLICT(session_date) DO NOTHING
            """,
            (session_date.isoformat(), started_at),
        )
        row = conn.execute(
            "SELECT id FROM chat_sessions WHERE session_date = ?",
            (session_date.isoformat(),),
        ).fetchone()
        conn.commit()
    if row is None:
        raise RuntimeError("failed to create daily chat session")
    return int(row[0])


def add_chat_message(
    session_id: int,
    role: str,
    content: str,
    created_at: str,
    goal_id: int | None = None,
    task_id: int | None = None,
) -> int:
    """Append one user, assistant, or system message to a daily session."""
    if role not in {"user", "assistant", "system"}:
        raise ValueError("invalid chat role")
    cleaned = (content or "").strip()
    if not cleaned:
        raise ValueError("chat message is empty")

    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_messages
                (session_id, role, content, created_at, goal_id, task_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, cleaned, created_at, goal_id, task_id),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_chat_messages_for_date(session_date: date) -> list[dict[str, object]]:
    """Return all retained messages for one local calendar date."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT m.id, m.session_id, m.role, m.content, m.created_at, m.goal_id, m.task_id
            FROM chat_messages AS m
            JOIN chat_sessions AS s ON s.id = m.session_id
            WHERE s.session_date = ?
            ORDER BY m.id ASC
            """,
            (session_date.isoformat(),),
        ).fetchall()
    return [dict(row) for row in rows]


def list_pending_chat_dates(before_date: date) -> list[date]:
    """Return retained chat dates older than the supplied local date."""
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT session_date
            FROM chat_sessions
            WHERE session_date < ?
            ORDER BY session_date ASC
            """,
            (before_date.isoformat(),),
        ).fetchall()
    return [date.fromisoformat(str(row[0])) for row in rows]


def mark_chat_session_failed(session_date: date, error_message: str) -> None:
    """Keep a failed session for retry and store a concise error."""
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE chat_sessions
            SET status = 'failed', last_error = ?
            WHERE session_date = ?
            """,
            (error_message[:2000], session_date.isoformat()),
        )
        conn.commit()


def save_daily_analysis_and_delete_chat(
    analysis_date: date,
    analysis: dict[str, Any],
    model_name: str,
    message_count: int,
    created_at: str,
    memory_candidates: list[dict[str, object]] | None = None,
    evidence: list[dict[str, object]] | None = None,
) -> None:
    """Atomically save analysis/candidates and remove the source raw chat."""
    list_fields = ("progress", "obstacles", "patterns", "next_actions")
    encoded = {
        field: json.dumps(analysis.get(field, []), ensure_ascii=False)
        for field in list_fields
    }

    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        session_row = conn.execute(
            "SELECT id FROM chat_sessions WHERE session_date = ?",
            (analysis_date.isoformat(),),
        ).fetchone()
        source_conversation = int(session_row[0]) if session_row else None
        source_messages = {
            int(row[0]): {
                "role": str(row[1]),
                "content": str(row[2]),
                "created_at": str(row[3]),
            }
            for row in conn.execute(
                """
                SELECT m.id, m.role, m.content, m.created_at
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.session_date = ?
                """,
                (analysis_date.isoformat(),),
            ).fetchall()
        }
        for item in evidence or []:
            message_id = item.get("message_id")
            source = (
                source_messages.get(message_id)
                if isinstance(message_id, int)
                else None
            )
            if source is None or source["role"] != "user":
                raise ValueError("Evidence 引用了不存在的用户消息")
            quote = str(item.get("quote", "")).strip()
            if not quote or quote not in source["content"]:
                raise ValueError("Evidence quote 与原始消息不一致")
        conn.execute(
            """
            INSERT INTO daily_analyses (
                analysis_date, summary, progress, obstacles, patterns,
                mood, next_actions, model_name, message_count, created_at,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(analysis_date) DO UPDATE SET
                summary = excluded.summary,
                progress = excluded.progress,
                obstacles = excluded.obstacles,
                patterns = excluded.patterns,
                mood = excluded.mood,
                next_actions = excluded.next_actions,
                model_name = excluded.model_name,
                message_count = excluded.message_count,
                created_at = excluded.created_at,
                confidence = excluded.confidence
            """,
            (
                analysis_date.isoformat(),
                analysis["summary"],
                encoded["progress"],
                encoded["obstacles"],
                encoded["patterns"],
                analysis["mood"],
                encoded["next_actions"],
                model_name,
                message_count,
                created_at,
                float(analysis.get("confidence", 0.5)),
            ),
        )
        report_id = int(
            conn.execute(
                "SELECT id FROM daily_analyses WHERE analysis_date = ?",
                (analysis_date.isoformat(),),
            ).fetchone()[0]
        )
        conn.execute(
            "DELETE FROM daily_report_evidence WHERE report_id = ?",
            (report_id,),
        )
        for item in evidence or []:
            source = source_messages[int(item["message_id"])]
            conn.execute(
                """
                INSERT INTO daily_report_evidence (
                    report_id, message_id, evidence_type, claim, quote,
                    message_created_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    item["message_id"],
                    item["evidence_type"],
                    item["claim"],
                    item["quote"],
                    source["created_at"],
                    created_at,
                ),
            )
        for candidate in memory_candidates or []:
            candidate_cursor = conn.execute(
                """
                INSERT INTO candidate_memories (
                    content, type, importance, confidence,
                    source_conversation, source_date, status, created_at,
                    source_report_id, created_reason
                )
                SELECT ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM candidate_memories
                    WHERE status = 'pending' AND type = ? AND content = ?
                )
                AND NOT EXISTS (
                    SELECT 1 FROM memories
                    WHERE status = 'active' AND type = ? AND content = ?
                )
                """,
                (
                    candidate["content"],
                    candidate["type"],
                    candidate["importance"],
                    candidate["confidence"],
                    source_conversation,
                    analysis_date.isoformat(),
                    created_at,
                    report_id,
                    str(candidate.get("created_reason", "")).strip()
                    or f"由 {analysis_date.isoformat()} 日报提出",
                    candidate["type"],
                    candidate["content"],
                    candidate["type"],
                    candidate["content"],
                ),
            )
            if candidate_cursor.rowcount > 0:
                candidate_id = int(candidate_cursor.lastrowid)
                evidence_message_ids = candidate.get(
                    "evidence_message_ids",
                    [],
                )
                if isinstance(evidence_message_ids, list):
                    for message_id in evidence_message_ids:
                        rows = conn.execute(
                            """
                            SELECT id FROM daily_report_evidence
                            WHERE report_id = ? AND message_id = ?
                            """,
                            (report_id, message_id),
                        ).fetchall()
                        if not rows:
                            raise ValueError(
                                "候选记忆引用的消息没有持久化 Evidence"
                            )
                        conn.executemany(
                            """
                            INSERT OR IGNORE INTO candidate_memory_evidence (
                                candidate_id, evidence_id
                            ) VALUES (?, ?)
                            """,
                            [(candidate_id, int(row[0])) for row in rows],
                        )
        conn.execute(
            "DELETE FROM chat_sessions WHERE session_date = ?",
            (analysis_date.isoformat(),),
        )
        conn.commit()


def list_memories(
    status: str = "active",
    memory_types: list[str] | None = None,
) -> list[dict[str, object]]:
    """List formal memories visible to the user."""
    query = "SELECT * FROM memories WHERE status = ?"
    values: list[object] = [status]
    if memory_types:
        placeholders = ", ".join("?" for _ in memory_types)
        query += f" AND type IN ({placeholders})"
        values.extend(memory_types)
    query += " ORDER BY importance DESC, confidence DESC, updated_at DESC"
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def get_memory(memory_id: int) -> dict[str, object] | None:
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
    return dict(row) if row else None


def update_memory(
    memory_id: int,
    memory_type: str,
    content: str,
    importance: float,
    status: str,
    updated_at: str,
) -> bool:
    with connect_db() as conn:
        cursor = conn.execute(
            """
            UPDATE memories
            SET type = ?, content = ?, importance = ?,
                status = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                memory_type,
                content,
                importance,
                status,
                updated_at,
                memory_id,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0


def search_memories(
    keywords: list[str],
    memory_types: list[str] | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """Keyword-search active formal memories; ranking happens in the retriever."""
    query = "SELECT * FROM memories WHERE status = 'active'"
    values: list[object] = []
    if memory_types:
        placeholders = ", ".join("?" for _ in memory_types)
        query += f" AND type IN ({placeholders})"
        values.extend(memory_types)
    if keywords:
        clauses = " OR ".join("content LIKE ?" for _ in keywords)
        query += f" AND ({clauses})"
        values.extend(f"%{keyword}%" for keyword in keywords)
    query += " ORDER BY importance DESC, confidence DESC LIMIT ?"
    values.append(limit)
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, values).fetchall()
    return [dict(row) for row in rows]


def mark_memories_used(memory_ids: list[int], used_at: str) -> None:
    if not memory_ids:
        return
    with connect_db() as conn:
        conn.executemany(
            """
            UPDATE memories
            SET use_count = use_count + 1, last_used_at = ?
            WHERE id = ? AND status = 'active'
            """,
            [(used_at, memory_id) for memory_id in memory_ids],
        )
        conn.commit()


def list_candidate_memories(
    status: str = "pending",
) -> list[dict[str, object]]:
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM candidate_memories
            WHERE status = ?
            ORDER BY id ASC
            """,
            (status,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_candidate_memory(candidate_id: int) -> dict[str, object] | None:
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM candidate_memories WHERE id = ?",
            (candidate_id,),
        ).fetchone()
    return dict(row) if row else None


def update_candidate_memory(
    candidate_id: int,
    memory_type: str,
    content: str,
    importance: float,
    confidence: float,
) -> bool:
    with connect_db() as conn:
        cursor = conn.execute(
            """
            UPDATE candidate_memories
            SET type = ?, content = ?, importance = ?, confidence = ?
            WHERE id = ? AND status = 'pending'
            """,
            (memory_type, content, importance, confidence, candidate_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def reject_candidate_memory(candidate_id: int, reviewed_at: str) -> bool:
    with connect_db() as conn:
        cursor = conn.execute(
            """
            UPDATE candidate_memories
            SET status = 'rejected', reviewed_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (reviewed_at, candidate_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def accept_candidate_memory(
    candidate_id: int,
    reviewed_at: str,
) -> int:
    """Promote a pending candidate to formal memory in one transaction."""
    with connect_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        candidate = conn.execute(
            """
            SELECT type, content, importance, source_report_id,
                   source_date, created_reason
            FROM candidate_memories
            WHERE id = ? AND status = 'pending'
            """,
            (candidate_id,),
        ).fetchone()
        if candidate is None:
            raise ValueError("候选记忆不存在或已处理")
        cursor = conn.execute(
            """
            INSERT INTO memories (
                type, content, importance, confidence, source,
                created_at, updated_at, status
            )
            VALUES (?, ?, ?, 0.9, ?, ?, ?, 'active')
            """,
            (
                candidate[0],
                candidate[1],
                candidate[2],
                f"candidate:{candidate_id}",
                reviewed_at,
                reviewed_at,
            ),
        )
        conn.execute(
            """
            UPDATE candidate_memories
            SET status = 'accepted', reviewed_at = ?
            WHERE id = ?
            """,
            (reviewed_at, candidate_id),
        )
        memory_id = int(cursor.lastrowid)
        source_id = (
            str(candidate[3])
            if candidate[3] is not None
            else str(candidate[4] or candidate_id)
        )
        source_type = (
            "daily_report"
            if candidate[3] is not None or candidate[4]
            else "candidate"
        )
        conn.execute(
            """
            INSERT INTO memory_sources (
                memory_id, source_type, source_id, created_reason, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                source_type,
                source_id,
                str(candidate[5] or "用户审核候选后创建"),
                reviewed_at,
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO memory_evidence (memory_id, evidence_id)
            SELECT ?, evidence_id
            FROM candidate_memory_evidence
            WHERE candidate_id = ?
            """,
            (memory_id, candidate_id),
        )
        conn.commit()
        return memory_id


def set_memory_status(
    memory_id: int,
    status: str,
    updated_at: str,
) -> bool:
    with connect_db() as conn:
        cursor = conn.execute(
            """
            UPDATE memories
            SET status = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, updated_at, memory_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_daily_analysis(analysis_date: date) -> dict[str, object] | None:
    """Return one saved daily analysis with JSON list fields decoded."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM daily_analyses WHERE analysis_date = ?",
            (analysis_date.isoformat(),),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    for field in ("progress", "obstacles", "patterns", "next_actions"):
        try:
            result[field] = json.loads(str(result[field]))
        except json.JSONDecodeError:
            result[field] = []
    result["evidence"] = get_daily_report_evidence(analysis_date)
    return result


def get_daily_report_evidence(
    analysis_date: date,
) -> list[dict[str, object]]:
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT e.id, e.report_id, e.message_id, e.evidence_type,
                   e.claim, e.quote, e.message_created_at, e.created_at
            FROM daily_report_evidence e
            JOIN daily_analyses r ON r.id = e.report_id
            WHERE r.analysis_date = ?
            ORDER BY e.evidence_type, e.id
            """,
            (analysis_date.isoformat(),),
        ).fetchall()
    return [dict(row) for row in rows]


def get_memory_provenance(memory_id: int) -> list[dict[str, object]]:
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        source_rows = conn.execute(
            """
            SELECT id, memory_id, source_type, source_id,
                   created_reason, created_at
            FROM memory_sources
            WHERE memory_id = ?
            ORDER BY id
            """,
            (memory_id,),
        ).fetchall()
        evidence_rows = conn.execute(
            """
            SELECT e.id, e.message_id, e.evidence_type, e.claim, e.quote,
                   e.message_created_at
            FROM memory_evidence me
            JOIN daily_report_evidence e ON e.id = me.evidence_id
            WHERE me.memory_id = ?
            ORDER BY e.id
            """,
            (memory_id,),
        ).fetchall()
    evidence = [dict(row) for row in evidence_rows]
    result = [dict(row) for row in source_rows]
    for source in result:
        source["evidence"] = evidence
    return result


def get_recent_daily_analyses(
    before_date: date,
    limit: int = 7,
) -> list[dict[str, object]]:
    """Return recent saved summaries for conversational context."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT analysis_date, summary, progress, obstacles, patterns, mood, next_actions
            FROM daily_analyses
            WHERE analysis_date < ?
            ORDER BY analysis_date DESC
            LIMIT ?
            """,
            (before_date.isoformat(), limit),
        ).fetchall()

    results: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        for field in ("progress", "obstacles", "patterns", "next_actions"):
            try:
                item[field] = json.loads(str(item[field]))
            except json.JSONDecodeError:
                item[field] = []
        results.append(item)
    return results


def get_daily_analyses_between(
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    """Return decoded daily analyses within an inclusive date range."""
    with connect_db() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT analysis_date, summary, progress, obstacles, patterns,
                   mood, next_actions, model_name, message_count, created_at
            FROM daily_analyses
            WHERE analysis_date BETWEEN ? AND ?
            ORDER BY analysis_date ASC
            """,
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

    results: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        for field in ("progress", "obstacles", "patterns", "next_actions"):
            try:
                item[field] = json.loads(str(item[field]))
            except json.JSONDecodeError:
                item[field] = []
        results.append(item)
    return results
