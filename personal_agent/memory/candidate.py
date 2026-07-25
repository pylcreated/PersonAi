from __future__ import annotations

from datetime import datetime
from typing import Callable

from personal_agent.core.clock import local_now
from personal_agent.memory.conflict import MemoryConflictDetector
from personal_agent.memory.models import (
    CandidateMemoryDraft,
    MemoryConflict,
)
from personal_agent.memory.repository import AgentRepository


class MemoryConflictError(ValueError):
    def __init__(self, conflicts: list[MemoryConflict]) -> None:
        super().__init__("候选记忆与现有记忆可能冲突，需要用户确认")
        self.conflicts = conflicts


class CandidateMemoryService:
    """User-controlled review workflow for AI-proposed memories."""

    def __init__(
        self,
        repository: AgentRepository,
        conflict_detector: MemoryConflictDetector,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.repository = repository
        self.conflict_detector = conflict_detector
        self.clock = clock

    def pending(self) -> list[dict[str, object]]:
        return self.repository.candidates("pending")

    def edit(
        self,
        candidate_id: int,
        *,
        memory_type: str,
        content: str,
        importance: float | None = None,
        confidence: float | None = None,
    ) -> bool:
        existing = self.repository.candidate(candidate_id)
        if existing is None or existing.get("status") != "pending":
            return False
        validated = CandidateMemoryDraft.from_mapping(
            {
                "type": memory_type,
                "content": content,
                "importance": (
                    existing["importance"] if importance is None else importance
                ),
                "confidence": (
                    existing["confidence"] if confidence is None else confidence
                ),
            }
        )
        return self.repository.update_candidate(
            candidate_id,
            validated.type,
            validated.content,
            validated.importance,
            validated.confidence,
        )

    def reject(self, candidate_id: int) -> bool:
        return self.repository.reject_candidate(
            candidate_id,
            self.clock().isoformat(),
        )

    def accept(self, candidate_id: int, *, force: bool = False) -> int:
        raw = self.repository.candidate(candidate_id)
        if raw is None or raw.get("status") != "pending":
            raise ValueError("候选记忆不存在或已处理")
        candidate = CandidateMemoryDraft.from_mapping(raw)
        conflicts = self.conflict_detector.detect(
            candidate,
            self.repository.memories("active", [candidate.type]),
        )
        if conflicts and not force:
            raise MemoryConflictError(conflicts)
        return self.repository.accept_candidate(
            candidate_id,
            self.clock().isoformat(),
        )
