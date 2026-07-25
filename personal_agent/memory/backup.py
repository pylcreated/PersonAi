from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import os
from pathlib import Path
import sqlite3

from personal_agent.core.clock import local_now


class DatabaseBackupManager:
    """Create verified SQLite backups and restore them without partial writes."""

    def __init__(
        self,
        database_path: str | Path,
        backups_dir: Path,
        *,
        retention: int = 30,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        if retention < 1:
            raise ValueError("retention 必须大于 0")
        target = str(database_path)
        if target.startswith("file:"):
            raise ValueError("共享内存 SQLite 不支持文件备份")
        self.database_path = Path(target).resolve()
        self.backups_dir = backups_dir.resolve()
        self.retention = retention
        self.clock = clock

    def create_backup(self) -> Path:
        if not self.database_path.is_file():
            raise FileNotFoundError(f"数据库不存在：{self.database_path}")
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.clock().strftime("%Y%m%d_%H%M%S_%f")
        destination = self.backups_dir / f"backup_{timestamp}.db"
        temporary = destination.with_suffix(".db.tmp")

        source_connection = sqlite3.connect(self.database_path)
        target_connection = sqlite3.connect(temporary)
        try:
            source_connection.backup(target_connection)
            target_connection.commit()
            self._assert_healthy(target_connection)
        except Exception:
            target_connection.close()
            source_connection.close()
            temporary.unlink(missing_ok=True)
            raise
        else:
            target_connection.close()
            source_connection.close()

        os.replace(temporary, destination)
        self._prune()
        return destination

    def restore(self, backup_name: str | Path) -> Path:
        source = self._resolve_backup(backup_name)
        source_connection = sqlite3.connect(source)
        try:
            self._assert_healthy(source_connection)
        finally:
            source_connection.close()

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.database_path.with_suffix(".restore.tmp")
        temporary.unlink(missing_ok=True)
        source_connection = sqlite3.connect(source)
        target_connection = sqlite3.connect(temporary)
        try:
            source_connection.backup(target_connection)
            target_connection.commit()
            self._assert_healthy(target_connection)
        except Exception:
            target_connection.close()
            source_connection.close()
            temporary.unlink(missing_ok=True)
            raise
        else:
            target_connection.close()
            source_connection.close()

        previous: Path | None = None
        if self.database_path.exists():
            self.backups_dir.mkdir(parents=True, exist_ok=True)
            timestamp = self.clock().strftime("%Y%m%d_%H%M%S_%f")
            previous = self.backups_dir / f"pre_restore_{timestamp}.db"
            os.replace(self.database_path, previous)
        try:
            os.replace(temporary, self.database_path)
        except Exception:
            if previous is not None and not self.database_path.exists():
                os.replace(previous, self.database_path)
            temporary.unlink(missing_ok=True)
            raise
        return self.database_path

    def list_backups(self) -> list[Path]:
        if not self.backups_dir.exists():
            return []
        return sorted(
            self.backups_dir.glob("backup_*.db"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )

    def _resolve_backup(self, backup_name: str | Path) -> Path:
        candidate = Path(backup_name)
        if not candidate.is_absolute():
            candidate = self.backups_dir / candidate
        resolved = candidate.resolve()
        if resolved.parent != self.backups_dir:
            raise ValueError("只能恢复 backups 目录中的直接子文件")
        if resolved.suffix.lower() != ".db" or not resolved.is_file():
            raise FileNotFoundError(f"备份不存在：{resolved}")
        return resolved

    def _prune(self) -> None:
        for expired in self.list_backups()[self.retention :]:
            expired.unlink()

    @staticmethod
    def _assert_healthy(connection: sqlite3.Connection) -> None:
        row = connection.execute("PRAGMA quick_check").fetchone()
        if row is None or row[0] != "ok":
            detail = row[0] if row else "无检查结果"
            raise sqlite3.DatabaseError(f"SQLite 完整性检查失败：{detail}")
