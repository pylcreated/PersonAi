from __future__ import annotations

from datetime import datetime
from typing import Callable

from personal_agent.core.clock import local_now
from personal_agent.memory.models import MEMORY_STATUSES
from personal_agent.memory.repository import AgentRepository


class MemoryLifecycleManager:
    """Explicit lifecycle operations; no automatic permanent deletion."""

    def __init__(
        self,
        repository: AgentRepository,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.repository = repository
        self.clock = clock

    def list(self, status: str = "active") -> list[dict[str, object]]:
        if status not in MEMORY_STATUSES:
            raise ValueError(f"无效记忆状态：{status}")
        return self.repository.memories(status)

    def archive(self, memory_id: int) -> bool:
        return self._set_status(memory_id, "archived")

    def expire(self, memory_id: int) -> bool:
        return self._set_status(memory_id, "expired")

    def delete(self, memory_id: int) -> bool:
        return self._set_status(memory_id, "deleted")

    def _set_status(self, memory_id: int, status: str) -> bool:
        return self.repository.set_memory_status(
            memory_id,
            status,
            self.clock().isoformat(),
        )
