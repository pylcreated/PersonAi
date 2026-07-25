from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from personal_agent.interfaces.web import PersonalAgentWebServer, create_handler
from personal_agent.memory import database
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.memory.service import MemoryManagementService


CHINA_TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 25, 15, 0, tzinfo=CHINA_TZ)


def add_memory() -> int:
    with database.connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories (
                type, content, importance, confidence, source,
                created_at, updated_at, status
            ) VALUES (
                'project', '正在开发 Personal Agent', 0.8, 0.9,
                'candidate:2', ?, ?, 'active'
            )
            """,
            (NOW.isoformat(), NOW.isoformat()),
        )
        memory_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO memory_sources (
                memory_id, source_type, source_id, created_reason, created_at
            ) VALUES (?, 'daily_report', '2026-07-24', '日报提出', ?)
            """,
            (memory_id, NOW.isoformat()),
        )
        conn.commit()
    return memory_id


@contextmanager
def memory_api(repository):
    service = MemoryManagementService(
        repository,
        MemoryLifecycleManager(repository, clock=lambda: NOW),
        clock=lambda: NOW,
    )
    application = SimpleNamespace(memory_management=service)
    web_service = PersonalAgentWebServer(application)
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(web_service),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    data = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    request = Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_memory_http_query_update_detail_and_delete(repository) -> None:
    memory_id = add_memory()
    with memory_api(repository) as base_url:
        status, listing = request_json(base_url, "/api/memory?status=active")
        assert status == 200
        assert listing["memories"][0]["id"] == memory_id

        status, detail = request_json(base_url, f"/api/memory/{memory_id}")
        assert status == 200
        assert detail["provenance"][0]["source_id"] == "2026-07-24"

        status, updated = request_json(
            base_url,
            f"/api/memory/{memory_id}",
            method="PUT",
            payload={
                "type": "preference",
                "content": "偏好本地优先",
                "importance": 0.7,
                "status": "active",
            },
        )
        assert status == 200
        assert updated["type"] == "preference"
        assert updated["content"] == "偏好本地优先"

        status, deleted = request_json(
            base_url,
            f"/api/memory/{memory_id}",
            method="DELETE",
        )
        assert status == 200
        assert deleted["status"] == "deleted"

        status, deleted_listing = request_json(
            base_url,
            "/api/memory?status=deleted",
        )
        assert status == 200
        assert deleted_listing["memories"][0]["id"] == memory_id


def test_memory_http_rejects_invalid_update(repository) -> None:
    memory_id = add_memory()
    with memory_api(repository) as base_url:
        status, payload = request_json(
            base_url,
            f"/api/memory/{memory_id}",
            method="PUT",
            payload={"importance": 4},
        )

    assert status == 400
    assert "重要性" in payload["error"]
