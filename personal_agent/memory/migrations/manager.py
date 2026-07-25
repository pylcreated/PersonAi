from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
import re
import sqlite3


MIGRATION_NAME = re.compile(r"^(?P<version>\d{3,})_[a-z0-9_]+\.sql$")


class MigrationManager:
    """Apply ordered SQLite migrations, one atomic transaction at a time."""

    def __init__(
        self,
        connection_factory: Callable[[], sqlite3.Connection],
        migrations_dir: Path | None = None,
    ) -> None:
        self.connection_factory = connection_factory
        self.migrations_dir = migrations_dir or Path(__file__).parent

    def migrate(self) -> list[int]:
        migrations = self._discover()
        with self.connection_factory() as connection:
            self._ensure_version_table(connection)
            applied = self._applied_versions(connection)

        completed: list[int] = []
        for version, path in migrations:
            if version in applied:
                continue
            self._apply_one(version, path)
            completed.append(version)
        return completed

    def current_version(self) -> int:
        with self.connection_factory() as connection:
            self._ensure_version_table(connection)
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_version"
            ).fetchone()
        return int(row[0])

    def _discover(self) -> list[tuple[int, Path]]:
        migrations: list[tuple[int, Path]] = []
        seen: set[int] = set()
        for path in self.migrations_dir.glob("*.sql"):
            match = MIGRATION_NAME.fullmatch(path.name)
            if match is None:
                raise ValueError(f"非法 migration 文件名：{path.name}")
            version = int(match.group("version"))
            if version in seen:
                raise ValueError(f"重复的 migration 版本：{version}")
            seen.add(version)
            migrations.append((version, path))
        migrations.sort(key=lambda item: item[0])
        return migrations

    @staticmethod
    def _ensure_version_table(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL UNIQUE,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.commit()

    @staticmethod
    def _applied_versions(connection: sqlite3.Connection) -> set[int]:
        rows = connection.execute(
            "SELECT version FROM schema_version"
        ).fetchall()
        return {int(row[0]) for row in rows}

    def _apply_one(self, version: int, path: Path) -> None:
        sql = path.read_text(encoding="utf-8")
        with self.connection_factory() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                for statement in self._statements(sql):
                    command = statement.lstrip().split(None, 1)[0].upper()
                    if command in {"BEGIN", "COMMIT", "ROLLBACK", "END"}:
                        raise ValueError(
                            f"migration {path.name} 不允许自行控制事务"
                        )
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO schema_version (version, applied_at)
                    VALUES (?, ?)
                    """,
                    (version, datetime.now(UTC).isoformat()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _statements(sql: str) -> Iterator[str]:
        buffer: list[str] = []
        for line in sql.splitlines():
            if not buffer and (
                not line.strip() or line.lstrip().startswith("--")
            ):
                continue
            buffer.append(line)
            candidate = "\n".join(buffer).strip()
            if sqlite3.complete_statement(candidate):
                yield candidate
                buffer.clear()
        if any(line.strip() for line in buffer):
            raise ValueError("migration SQL 末尾存在不完整语句")
