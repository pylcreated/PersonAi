from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from personal_agent.memory import SQLiteAgentRepository, database
from personal_agent.memory.migrations import MigrationManager


def test_new_database_is_initialized_with_version(
    isolated_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = isolated_root / "new.db"
    monkeypatch.setattr(database, "DB_PATH", path)

    SQLiteAgentRepository().initialize()

    with sqlite3.connect(path) as connection:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert version == 4
    assert {
        "goals",
        "chat_messages",
        "daily_analyses",
        "daily_report_evidence",
        "memories",
        "memory_sources",
        "personal_tasks",
    } <= tables


def test_legacy_database_is_upgraded_without_losing_data(
    isolated_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = isolated_root / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        connection.execute(
            """
            INSERT INTO goals (title, created_at, active)
            VALUES ('保留的旧目标', '2026-07-01T00:00:00+00:00', 1)
            """
        )
    monkeypatch.setattr(database, "DB_PATH", path)

    repository = SQLiteAgentRepository()
    repository.initialize()

    assert repository.active_goals()[0]["title"] == "保留的旧目标"
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT version FROM schema_version"
        ).fetchall() == [(1,), (2,), (3,), (4,)]
        assert connection.execute(
            "SELECT COUNT(*) FROM chat_sessions"
        ).fetchone()[0] == 0


def test_failed_migration_rolls_back_and_can_be_retried(
    isolated_root: Path,
) -> None:
    path = isolated_root / "rollback.db"
    migrations = isolated_root / "migrations"
    migrations.mkdir()
    (migrations / "001_initial.sql").write_text(
        "CREATE TABLE stable (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    failing = migrations / "002_add_feature.sql"
    failing.write_text(
        """
        CREATE TABLE partial_change (id INTEGER PRIMARY KEY);
        INSERT INTO missing_table (id) VALUES (1);
        """,
        encoding="utf-8",
    )

    def connect() -> sqlite3.Connection:
        return sqlite3.connect(path)

    manager = MigrationManager(connect, migrations)
    with pytest.raises(sqlite3.OperationalError):
        manager.migrate()

    with connect() as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        versions = connection.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
    assert "stable" in names
    assert "partial_change" not in names
    assert versions == [(1,)]

    failing.write_text(
        "CREATE TABLE recovered (id INTEGER PRIMARY KEY);",
        encoding="utf-8",
    )
    assert manager.migrate() == [2]
    assert manager.current_version() == 2


def test_repeated_migration_is_a_noop_and_preserves_rows(
    isolated_root: Path,
) -> None:
    path = isolated_root / "repeat.db"

    def connect() -> sqlite3.Connection:
        return sqlite3.connect(path)

    manager = MigrationManager(connect)
    assert manager.migrate() == [1, 2, 3, 4]
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO goals (title, created_at, active)
            VALUES ('不能重复破坏', '2026-07-01T00:00:00+00:00', 1)
            """
        )

    assert manager.migrate() == []
    with connect() as connection:
        assert connection.execute(
            "SELECT title FROM goals"
        ).fetchall() == [("不能重复破坏",)]
        assert connection.execute(
            "SELECT COUNT(*) FROM schema_version WHERE version = 1"
        ).fetchone()[0] == 1
