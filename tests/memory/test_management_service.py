from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from personal_agent.memory import database
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.memory.service import MemoryManagementService


CHINA_TZ = timezone(timedelta(hours=8))
NOW = datetime(2026, 7, 25, 14, 30, tzinfo=CHINA_TZ)


def add_memory(
    *,
    memory_type: str = "project",
    content: str = "正在开发 Personal Agent",
    status: str = "active",
) -> int:
    with database.connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories (
                type, content, importance, confidence, source,
                created_at, updated_at, status
            ) VALUES (?, ?, 0.8, 0.9, 'candidate:1', ?, ?, ?)
            """,
            (
                memory_type,
                content,
                NOW.isoformat(),
                NOW.isoformat(),
                status,
            ),
        )
        memory_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO memory_sources (
                memory_id, source_type, source_id, created_reason, created_at
            ) VALUES (?, 'daily_report', '2026-07-24', ?, ?)
            """,
            (
                memory_id,
                "由 2026-07-24 日报提出",
                NOW.isoformat(),
            ),
        )
        conn.commit()
    return memory_id


def build_service(repository) -> MemoryManagementService:
    lifecycle = MemoryLifecycleManager(repository, clock=lambda: NOW)
    return MemoryManagementService(
        repository,
        lifecycle,
        clock=lambda: NOW,
    )


def test_memory_management_lists_and_returns_provenance(repository) -> None:
    memory_id = add_memory()
    service = build_service(repository)

    items = service.list("active")
    detail = service.detail(memory_id)

    assert [item["id"] for item in items] == [memory_id]
    assert detail["content"] == "正在开发 Personal Agent"
    assert detail["provenance"][0]["source_type"] == "daily_report"
    assert detail["provenance"][0]["source_id"] == "2026-07-24"
    assert detail["evidence"] == []


def test_memory_management_updates_allowed_fields(repository) -> None:
    memory_id = add_memory()
    service = build_service(repository)

    result = service.update(
        memory_id,
        {
            "type": "preference",
            "content": "偏好安静、克制的界面",
            "importance": 0.65,
            "status": "archived",
        },
    )

    assert result["type"] == "preference"
    assert result["content"] == "偏好安静、克制的界面"
    assert result["importance"] == pytest.approx(0.65)
    assert result["status"] == "archived"
    assert result["provenance"][0]["source_id"] == "2026-07-24"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"type": "unknown"}, "无效记忆类型"),
        ({"content": "   "}, "记忆内容不能为空"),
        ({"importance": 2}, "记忆重要性"),
        ({"status": "pending"}, "无效记忆状态"),
    ],
)
def test_memory_management_rejects_invalid_updates(
    repository,
    payload,
    message,
) -> None:
    memory_id = add_memory()
    service = build_service(repository)

    with pytest.raises(ValueError, match=message):
        service.update(memory_id, payload)


def test_memory_management_soft_deletes_and_keeps_provenance(repository) -> None:
    memory_id = add_memory()
    service = build_service(repository)

    result = service.delete(memory_id)
    detail = service.detail(memory_id)

    assert result == {
        "id": memory_id,
        "status": "deleted",
        "deleted": True,
    }
    assert detail["status"] == "deleted"
    assert detail["provenance"][0]["created_reason"] == "由 2026-07-24 日报提出"
    assert service.list("active") == []
    assert service.list("deleted")[0]["id"] == memory_id
