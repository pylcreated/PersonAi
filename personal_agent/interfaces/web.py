from __future__ import annotations

import json
import logging
import mimetypes
import re
import threading
from datetime import date, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from personal_agent.core.agent import week_start
from personal_agent.core.clock import local_now
from personal_agent.config import get_config
from personal_agent.config.settings import (
    save_model_runtime_config,
    save_runtime_config,
)
from personal_agent.memory.candidate import MemoryConflictError

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_ROOT = PROJECT_ROOT / "ui"
API_VERSION = 7


def _json_safe(value: Any) -> Any:
    if isinstance(value, (date,)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


class PersonalAgentWebServer:
    """Local-only HTTP adapter for the existing application services."""

    def __init__(self, application: Any) -> None:
        self.application = application
        self.analysis_lock = threading.Lock()

    def initialize(self) -> None:
        repository = self.application.repository
        repository.initialize()
        settings = repository.settings()
        if settings.get("setup_complete"):
            reminder_hour = int(settings.get("reminder_hour") or 20)
            self.application.scheduler.configure(reminder_hour)
            self.application.scheduler.start()
        threading.Thread(
            target=self._run_startup_analysis,
            daemon=True,
            name="personal-agent-startup-analysis",
        ).start()

    def _run_startup_analysis(self) -> None:
        try:
            self.analyze_pending()
        except Exception:
            logger.exception("Startup analysis catch-up failed")

    def shutdown(self) -> None:
        self.application.scheduler.stop()

    def dashboard(self) -> dict[str, Any]:
        today = local_now().date()
        repository = self.application.repository
        config = get_config()
        return {
            "date": today.isoformat(),
            "goals": repository.active_goals(),
            "tasks": repository.tasks_for_week(week_start(today)),
            "messages": repository.messages_for_date(today),
            "memory_candidates": self.application.candidate_memories.pending(),
            "memories": self.application.memory_lifecycle.list("active"),
            "daily_summaries": repository.recent_analyses(
                today + timedelta(days=1),
                7,
            ),
            "settings": repository.settings(),
            "pending_analysis_dates": [
                value.isoformat()
                for value in repository.pending_chat_dates(today)
            ],
            "analysis_running": self.analysis_lock.locked(),
            "model": {
                "provider": config.llm_provider,
                "name": self.application.agent.llm.model_name,
                "configured_name": config.llm_model_name,
            },
        }

    def chat(self, message: str) -> dict[str, str]:
        return {"reply": self.application.agent.chat(message)}

    def daily_report(self, requested_date: str | None = None) -> dict[str, Any]:
        repository = self.application.repository
        if requested_date:
            report_date = date.fromisoformat(requested_date)
            report = repository.daily_analysis(report_date)
        else:
            reports = repository.recent_analyses(
                local_now().date() + timedelta(days=1),
                1,
            )
            report = reports[0] if reports else None
            report_date = (
                date.fromisoformat(str(report["analysis_date"]))
                if report
                else local_now().date()
            )
        if report is None:
            raise LookupError("当前还没有可查看的日报")
        report["evidence"] = repository.report_evidence(report_date)
        return report

    def weekly_report(self) -> dict[str, str]:
        start = week_start(local_now().date())
        return {
            "week_start": start.isoformat(),
            "report": self.application.weekly_review.generate(start),
        }

    def add_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        description = str(payload.get("description") or "").strip()
        scope = str(payload.get("scope") or "week")
        if not description:
            raise ValueError("任务内容不能为空")
        if scope not in {"day", "week"}:
            raise ValueError("任务类型必须是今天或本周")
        today = local_now().date()
        task_id = self.application.repository.add_personal_task(
            description,
            week_start(today),
            scope,
            today if scope == "day" else None,
        )
        return {"id": task_id, "scope": scope, "created": True}

    def add_goal(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title") or "").strip()
        if not title:
            raise ValueError("目标名称不能为空")
        goal_id = self.application.repository.add_goal(title)
        return {"id": goal_id, "title": title, "created": True}

    def set_task(self, task_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        completed = bool(payload.get("completed"))
        updated = self.application.repository.set_task_completed(task_id, completed)
        if not updated:
            raise LookupError("没有找到该任务")
        return {"id": task_id, "completed": completed}

    def review_memory(self, candidate_id: int, action: str) -> dict[str, Any]:
        if action == "accept":
            memory_id = self.application.candidate_memories.accept(candidate_id)
            return {"candidate_id": candidate_id, "memory_id": memory_id}
        if action == "reject":
            updated = self.application.candidate_memories.reject(candidate_id)
            if not updated:
                raise LookupError("候选记忆不存在或已处理")
            return {"candidate_id": candidate_id, "rejected": True}
        raise ValueError("不支持的审核操作")

    def update_reminder(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            hour = int(payload.get("hour"))
        except (TypeError, ValueError) as exc:
            raise ValueError("提醒时间必须是 0-23 之间的整数") from exc
        if not 0 <= hour <= 23:
            raise ValueError("提醒时间必须是 0-23 之间的整数")
        save_runtime_config(hour)
        self.application.repository.save_settings(reminder_hour=hour)
        self.application.scheduler.configure(hour)
        return {"hour": hour, "updated": True}

    def update_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_name = str(payload.get("model_name") or "").strip()
        save_model_runtime_config(model_name)
        return {
            "model_name": model_name,
            "updated": True,
            "restart_required": True,
        }

    def list_backups(self) -> dict[str, Any]:
        items = self.application.backup_manager.list_backups()
        return {
            "backups": [
                {
                    "name": path.name,
                    "size": path.stat().st_size,
                    "modified_at": path.stat().st_mtime,
                }
                for path in items
            ],
            "retention": self.application.backup_manager.retention,
        }

    def create_backup(self) -> dict[str, Any]:
        path = self.application.backup_manager.create_backup()
        return {"name": path.name, "created": True}

    def analyze_pending(self) -> dict[str, Any]:
        if not self.analysis_lock.acquire(blocking=False):
            return {"running": True, "processed_dates": []}
        try:
            completed = self.application.daily_analysis.process_pending()
            return {
                "running": False,
                "processed_dates": [value.isoformat() for value in completed],
            }
        finally:
            self.analysis_lock.release()


def create_handler(service: PersonalAgentWebServer) -> type[BaseHTTPRequestHandler]:
    class RequestHandler(BaseHTTPRequestHandler):
        server_version = "PersonalAgent/0.35"

        def log_message(self, format: str, *args: object) -> None:
            logger.info("%s - %s", self.address_string(), format % args)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/health":
                self._send_json(
                    {
                        "ok": True,
                        "service": "personal-agent",
                        "api_version": API_VERSION,
                    }
                )
                return
            if path == "/api/dashboard":
                self._api_call(service.dashboard)
                return
            if path == "/api/daily":
                requested = parse_qs(parsed.query).get("date", [None])[0]
                self._api_call(service.daily_report, requested)
                return
            if path == "/api/backups":
                self._api_call(service.list_backups)
                return
            self._serve_static(path)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            payload = self._read_json()
            if payload is None:
                return
            if path == "/api/chat":
                self._api_call(service.chat, str(payload.get("message") or ""))
                return
            if path == "/api/tasks":
                self._api_call(service.add_task, payload, success=HTTPStatus.CREATED)
                return
            if path == "/api/goals":
                self._api_call(service.add_goal, payload, success=HTTPStatus.CREATED)
                return
            if path == "/api/weekly":
                self._api_call(service.weekly_report)
                return
            if path == "/api/settings/reminder":
                self._api_call(service.update_reminder, payload)
                return
            if path == "/api/settings/model":
                self._api_call(service.update_model, payload)
                return
            if path == "/api/backups":
                self._api_call(service.create_backup, success=HTTPStatus.CREATED)
                return
            if path == "/api/memory/analyze":
                self._api_call(service.analyze_pending)
                return

            task_match = re.fullmatch(r"/api/tasks/(-?\d+)", path)
            if task_match:
                self._api_call(service.set_task, int(task_match.group(1)), payload)
                return

            memory_match = re.fullmatch(
                r"/api/memories/(\d+)/(accept|reject)",
                path,
            )
            if memory_match:
                self._api_call(
                    service.review_memory,
                    int(memory_match.group(1)),
                    memory_match.group(2),
                )
                return
            self._send_json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)

        def _api_call(
            self,
            function: Any,
            *args: Any,
            success: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            try:
                self._send_json(function(*args), success)
            except MemoryConflictError as exc:
                self._send_json(
                    {
                        "error": str(exc),
                        "conflicts": [
                            {
                                "memory_id": item.old_memory_id,
                                "content": item.old_content,
                            }
                            for item in exc.conflicts
                        ],
                    },
                    HTTPStatus.CONFLICT,
                )
            except (ValueError, LookupError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                logger.exception("Web API request failed")
                self._send_json(
                    {"error": f"服务暂时不可用：{exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def _read_json(self) -> dict[str, Any] | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 1_000_000:
                    raise ValueError("请求内容为空或过大")
                raw = self.rfile.read(length).decode("utf-8")
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    raise ValueError("请求必须是 JSON 对象")
                return payload
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return None

        def _serve_static(self, request_path: str) -> None:
            relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
            candidate = (UI_ROOT / relative).resolve()
            try:
                candidate.relative_to(UI_ROOT.resolve())
            except ValueError:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not candidate.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            content = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)

        def _send_json(
            self,
            payload: Any,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            content = json.dumps(
                payload,
                ensure_ascii=False,
                default=_json_safe,
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

    return RequestHandler


def run_web_server(
    application: Any,
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    if not UI_ROOT.joinpath("index.html").is_file():
        raise FileNotFoundError(f"UI 入口不存在：{UI_ROOT / 'index.html'}")
    service = PersonalAgentWebServer(application)
    service.initialize()
    server = ThreadingHTTPServer((host, port), create_handler(service))
    print("Personal Agent Web 已启动")
    print(f"UI 地址：http://{host}:{port}")
    print("保持此窗口运行；按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止 Web 服务...")
    finally:
        server.server_close()
        service.shutdown()
