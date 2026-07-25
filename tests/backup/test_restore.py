from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from personal_agent.analysis import DailyAnalysisService
from personal_agent.llm.mock import MockLLMClient
from personal_agent.memory import (
    DatabaseBackupManager,
    DailyMemoryAnalyzer,
    SQLiteAgentRepository,
    database,
)

CHINA_TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 25, 0, 5, tzinfo=CHINA_TZ)


def _file_repository(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, SQLiteAgentRepository]:
    path = root / "database" / "agent.db"
    monkeypatch.setattr(database, "DB_PATH", path)
    repository = SQLiteAgentRepository()
    repository.initialize()
    return path, repository


def test_backup_is_created_and_retention_keeps_latest_files(
    isolated_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, repository = _file_repository(isolated_root, monkeypatch)
    repository.add_goal("备份目标")
    ticks = iter(
        [
            datetime(2026, 7, 24, 1, 0, 0, 1, tzinfo=CHINA_TZ),
            datetime(2026, 7, 24, 1, 0, 0, 2, tzinfo=CHINA_TZ),
            datetime(2026, 7, 24, 1, 0, 0, 3, tzinfo=CHINA_TZ),
        ]
    )
    manager = DatabaseBackupManager(
        path,
        isolated_root / "backups",
        retention=2,
        clock=lambda: next(ticks),
    )

    for _ in range(3):
        manager.create_backup()

    backups = manager.list_backups()
    assert len(backups) == 2
    assert backups[0].name.endswith("000003.db")
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute(
            "SELECT title FROM goals"
        ).fetchone()[0] == "备份目标"


def test_deleted_database_can_be_restored_with_user_data(
    isolated_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, repository = _file_repository(isolated_root, monkeypatch)
    goal_id = repository.add_goal("30 天连续使用")
    session_id = repository.get_or_create_session(
        date(2026, 7, 24),
        "2026-07-24T10:00:00+08:00",
    )
    repository.add_message(
        session_id,
        "user",
        "需要保留的聊天",
        "2026-07-24T10:00:00+08:00",
        goal_id=goal_id,
    )
    with database.connect_db() as connection:
        connection.execute(
            """
            INSERT INTO memories (
                type, content, importance, confidence, source,
                created_at, updated_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "project",
                "需要保留的记忆",
                0.8,
                0.9,
                "test",
                "2026-07-24T10:00:00+08:00",
                "2026-07-24T10:00:00+08:00",
                "active",
            ),
        )
    connection.close()
    manager = DatabaseBackupManager(path, isolated_root / "backups")
    backup = manager.create_backup()
    path.unlink()

    manager.restore(backup.name)
    repository.initialize()

    assert repository.active_goals()[0]["title"] == "30 天连续使用"
    assert (
        repository.messages_for_date(date(2026, 7, 24))[0]["content"]
        == "需要保留的聊天"
    )
    assert repository.memories()[0]["content"] == "需要保留的记忆"


def test_successful_daily_analysis_creates_post_commit_backup(
    isolated_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, repository = _file_repository(isolated_root, monkeypatch)
    chat_date = date(2026, 7, 24)
    session_id = repository.get_or_create_session(
        chat_date,
        "2026-07-24T10:00:00+08:00",
    )
    repository.add_message(
        session_id,
        "user",
        "今天完成了备份系统",
        "2026-07-24T10:00:00+08:00",
    )
    manager = DatabaseBackupManager(path, isolated_root / "backups")
    service = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(MockLLMClient()),
        clock=lambda: NOW,
        backup_after_success=manager.create_backup,
    )

    service.analyze_and_purge(chat_date)

    backup = manager.list_backups()[0]
    with sqlite3.connect(backup) as connection:
        report_count = connection.execute(
            "SELECT COUNT(*) FROM daily_analyses"
        ).fetchone()[0]
        message_count = connection.execute(
            "SELECT COUNT(*) FROM chat_messages"
        ).fetchone()[0]
    assert report_count == 1
    assert message_count == 0


def test_backup_failure_does_not_reverse_successful_daily_analysis(
    isolated_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, repository = _file_repository(isolated_root, monkeypatch)
    chat_date = date(2026, 7, 24)
    session_id = repository.get_or_create_session(
        chat_date,
        "2026-07-24T10:00:00+08:00",
    )
    repository.add_message(
        session_id,
        "user",
        "日报事务已经成功",
        "2026-07-24T10:00:00+08:00",
    )

    def fail_backup() -> None:
        raise OSError("磁盘空间不足")

    service = DailyAnalysisService(
        repository,
        DailyMemoryAnalyzer(MockLLMClient()),
        clock=lambda: NOW,
        backup_after_success=fail_backup,
    )

    result = service.analyze_and_purge(chat_date)

    assert result is not None
    assert repository.daily_analysis(chat_date) is not None
    assert repository.messages_for_date(chat_date) == []


def test_corrupt_backup_is_rejected_without_replacing_live_database(
    isolated_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, repository = _file_repository(isolated_root, monkeypatch)
    repository.add_goal("仍然存在")
    backups = isolated_root / "backups"
    backups.mkdir()
    corrupt = backups / "backup_corrupt.db"
    corrupt.write_bytes(b"not sqlite")
    manager = DatabaseBackupManager(path, backups)

    with pytest.raises(sqlite3.DatabaseError):
        manager.restore(corrupt.name)

    assert repository.active_goals()[0]["title"] == "仍然存在"
