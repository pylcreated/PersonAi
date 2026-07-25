from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from personal_agent.core.clock import local_now
from personal_agent.memory.lifecycle import MemoryLifecycleManager
from personal_agent.memory.models import MEMORY_STATUSES, MEMORY_TYPES
from personal_agent.memory.repository import AgentRepository


class MemoryManagementService:
    """User-control layer for existing formal memories."""

    def __init__(
        self,
        repository: AgentRepository,
        lifecycle: MemoryLifecycleManager,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.repository = repository
        self.lifecycle = lifecycle
        self.clock = clock

    def list(self, status: str = "active") -> list[dict[str, object]]:
        normalized = status.strip().lower()
        if normalized == "all":
            items = [
                memory
                for memory_status in MEMORY_STATUSES
                for memory in self.repository.memories(memory_status)
            ]
            return sorted(
                items,
                key=lambda item: (
                    str(item.get("updated_at") or ""),
                    int(item.get("id") or 0),
                ),
                reverse=True,
            )
        if normalized not in MEMORY_STATUSES:
            raise ValueError(f"无效记忆状态：{normalized}")
        return self.repository.memories(normalized)

    def detail(self, memory_id: int) -> dict[str, object]:
        memory = self.repository.memory(memory_id)
        if memory is None:
            raise LookupError("没有找到该长期记忆")
        provenance = self.repository.memory_provenance(memory_id)
        evidence_by_id: dict[int, dict[str, object]] = {}
        for source in provenance:
            for item in source.get("evidence", []):
                if isinstance(item, dict) and item.get("id") is not None:
                    evidence_by_id[int(item["id"])] = item
        return {
            **memory,
            "provenance": provenance,
            "evidence": list(evidence_by_id.values()),
        }

    def update(
        self,
        memory_id: int,
        payload: dict[str, Any],
    ) -> dict[str, object]:
        current = self.repository.memory(memory_id)
        if current is None:
            raise LookupError("没有找到该长期记忆")

        memory_type = str(payload.get("type", current["type"])).strip().lower()
        content = str(payload.get("content", current["content"])).strip()
        status = str(payload.get("status", current["status"])).strip().lower()
        try:
            importance = float(payload.get("importance", current["importance"]))
        except (TypeError, ValueError) as exc:
            raise ValueError("记忆重要性必须是 0-1 之间的数字") from exc

        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"无效记忆类型：{memory_type}")
        if not content:
            raise ValueError("记忆内容不能为空")
        if len(content) > 4000:
            raise ValueError("记忆内容不能超过 4000 个字符")
        if status not in MEMORY_STATUSES:
            raise ValueError(f"无效记忆状态：{status}")
        if not 0 <= importance <= 1:
            raise ValueError("记忆重要性必须是 0-1 之间的数字")

        updated = self.repository.update_memory(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            importance=importance,
            status=status,
            updated_at=self.clock().isoformat(),
        )
        if not updated:
            raise LookupError("没有找到该长期记忆")
        return self.detail(memory_id)

    def delete(self, memory_id: int) -> dict[str, object]:
        current = self.repository.memory(memory_id)
        if current is None:
            raise LookupError("没有找到该长期记忆")
        if current["status"] != "deleted" and not self.lifecycle.delete(memory_id):
            raise LookupError("没有找到该长期记忆")
        return {
            "id": memory_id,
            "status": "deleted",
            "deleted": True,
        }
