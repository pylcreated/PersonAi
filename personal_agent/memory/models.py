from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MEMORY_TYPES = {
    "profile",
    "preference",
    "goal",
    "project",
    "skill",
    "experience",
}
MEMORY_STATUSES = {"active", "expired", "archived", "deleted"}
CANDIDATE_STATUSES = {"pending", "accepted", "rejected"}
EVIDENCE_TYPES = {
    "summary",
    "progress",
    "obstacle",
    "pattern",
    "mood",
    "next_action",
}


def _score(value: object, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return min(1.0, max(0.0, result))


@dataclass(frozen=True)
class CandidateMemoryDraft:
    type: str
    content: str
    confidence: float = 0.5
    importance: float = 0.5
    evidence_message_ids: tuple[int, ...] = ()
    created_reason: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "CandidateMemoryDraft":
        memory_type = str(value.get("type", "")).strip().lower()
        content = str(value.get("content", "")).strip()
        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"无效记忆类型：{memory_type}")
        if not content:
            raise ValueError("候选记忆内容不能为空")
        raw_evidence_ids = value.get("evidence_message_ids", [])
        if not isinstance(raw_evidence_ids, (list, tuple)) or not all(
            isinstance(item, int) and item > 0 for item in raw_evidence_ids
        ):
            raise ValueError("候选记忆 evidence_message_ids 必须是正整数数组")
        return cls(
            type=memory_type,
            content=content,
            confidence=_score(value.get("confidence"), 0.5),
            importance=_score(value.get("importance"), 0.5),
            evidence_message_ids=tuple(dict.fromkeys(raw_evidence_ids)),
            created_reason=str(value.get("created_reason", "")).strip(),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "content": self.content,
            "confidence": self.confidence,
            "importance": self.importance,
            "evidence_message_ids": list(self.evidence_message_ids),
            "created_reason": self.created_reason,
        }


@dataclass(frozen=True)
class EvidenceDraft:
    evidence_type: str
    claim: str
    message_id: int
    quote: str
    message_created_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_type": self.evidence_type,
            "claim": self.claim,
            "message_id": self.message_id,
            "quote": self.quote,
            "message_created_at": self.message_created_at,
        }


@dataclass(frozen=True)
class MemoryConflict:
    old_memory_id: int
    old_content: str
    new_content: str
    reason: str
