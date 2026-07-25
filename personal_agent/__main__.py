from __future__ import annotations

import argparse
import logging

from personal_agent.bootstrap import create_application
from personal_agent.interfaces.web import run_web_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="personal_agent")
    subcommands = parser.add_subparsers(dest="command")
    subcommands.add_parser("backup", help="立即创建数据库备份")
    subcommands.add_parser("backups", help="列出可恢复的数据库备份")
    web = subcommands.add_parser("web", help="启动本地 Web UI 和 API")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    restore = subcommands.add_parser("restore", help="从备份恢复数据库")
    restore.add_argument("filename", help="data/backups 中的备份文件名")
    restore.add_argument(
        "--yes",
        action="store_true",
        help="跳过交互确认",
    )
    return parser


def main() -> None:
    """Create and start the local Personal Agent application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    arguments = build_parser().parse_args()
    application = create_application()

    if arguments.command == "web":
        run_web_server(application, arguments.host, arguments.port)
        return
    if arguments.command == "backup":
        application.repository.initialize()
        path = application.backup_manager.create_backup()
        print(f"数据库备份已生成：{path}")
        return
    if arguments.command == "backups":
        backups = application.backup_manager.list_backups()
        if not backups:
            print("当前没有数据库备份。")
        else:
            print("可用数据库备份：")
            for path in backups:
                print(f"- {path.name}")
        return
    if arguments.command == "restore":
        if not arguments.yes:
            confirmation = input(
                "恢复会替换当前数据库。请输入 RESTORE 继续："
            ).strip()
            if confirmation != "RESTORE":
                print("已取消恢复。")
                return
        path = application.backup_manager.restore(arguments.filename)
        application.repository.initialize()
        print(f"数据库恢复完成：{path}")
        return

    application.run()


if __name__ == "__main__":
    main()
