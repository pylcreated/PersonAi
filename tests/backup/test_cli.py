from __future__ import annotations

from personal_agent.__main__ import build_parser


def test_backup_cli_commands_are_parseable() -> None:
    backup = build_parser().parse_args(["backup"])
    restore = build_parser().parse_args(
        ["restore", "backup_20260724.db", "--yes"]
    )

    assert backup.command == "backup"
    assert restore.command == "restore"
    assert restore.filename == "backup_20260724.db"
    assert restore.yes is True
