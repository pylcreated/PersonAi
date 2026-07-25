from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Callable, Protocol

from personal_agent.core.clock import local_now
from personal_agent.memory.repository import AgentRepository


class MemorySearchBackend(Protocol):
    """Extension point for future keyword, FTS, or embedding search."""

    def search_memories(
        self,
        keywords: list[str],
        memory_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]: ...

    def mark_memories_used(self, memory_ids: list[int], used_at: str) -> None: ...


class MemoryRetriever:
    """Transparent v1 keyword retriever with deterministic ranking."""

    PERSONAL_MARKERS = (
        "我",
        "我的",
        "之前",
        "以前",
        "记得",
        "偏好",
        "目标",
        "项目",
        "适合",
        "下一步",
    )

    def __init__(
        self,
        backend: MemorySearchBackend,
        clock: Callable[[], datetime] = local_now,
    ) -> None:
        self.backend = backend
        self.clock = clock

    def retrieve(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        if not self.should_retrieve(query):
            return []
        keywords = self.extract_keywords(query)
        candidates = self.backend.search_memories(
            keywords,
            self.select_types(query),
            limit=50,
        )
        ranked = sorted(
            candidates,
            key=lambda item: self._score(query, item),
            reverse=True,
        )[:limit]
        self.backend.mark_memories_used(
            [int(item["id"]) for item in ranked],
            self.clock().isoformat(),
        )
        return ranked

    def should_retrieve(self, query: str) -> bool:
        normalized = query.strip().casefold()
        return any(marker.casefold() in normalized for marker in self.PERSONAL_MARKERS)

    @staticmethod
    def select_types(query: str) -> list[str] | None:
        mapping = {
            "项目": ["project", "goal", "experience", "skill"],
            "目标": ["goal", "project"],
            "偏好": ["preference", "profile"],
            "喜欢": ["preference"],
            "技能": ["skill", "experience"],
            "岗位": ["skill", "experience", "goal", "profile"],
            "之前": None,
        }
        for marker, types in mapping.items():
            if marker in query:
                return types
        return None

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        words = re.findall(r"[A-Za-z0-9_]{2,}", query.casefold())
        chinese_segments = re.findall(r"[\u4e00-\u9fff]+", query)
        bigrams = [
            segment[index : index + 2]
            for segment in chinese_segments
            for index in range(max(0, len(segment) - 1))
        ]
        ignored = {"我的", "怎么", "什么", "之前", "现在", "下一", "一步"}
        result: list[str] = []
        for token in words + bigrams:
            if token not in ignored and token not in result:
                result.append(token)
        return result[:12]

    def _score(self, query: str, memory: dict[str, object]) -> float:
        query_terms = set(self.extract_keywords(query))
        content_terms = set(self.extract_keywords(str(memory.get("content", ""))))
        similarity = (
            len(query_terms & content_terms) / max(1, len(query_terms))
            if query_terms
            else 0.0
        )
        importance = float(memory.get("importance", 0.5))
        confidence = float(memory.get("confidence", 0.5))
        recency = self._recency_score(memory.get("last_used_at"))
        return (
            similarity * 0.45
            + importance * 0.25
            + confidence * 0.20
            + recency * 0.10
        )

    def _recency_score(self, last_used_at: object) -> float:
        if not last_used_at:
            return 0.0
        try:
            used = datetime.fromisoformat(str(last_used_at))
            now = self.clock()
            if used.tzinfo is None:
                used = used.replace(tzinfo=timezone.utc)
            days = max(0.0, (now - used).total_seconds() / 86400)
            return max(0.0, 1.0 - days / 30)
        except ValueError:
            return 0.0
