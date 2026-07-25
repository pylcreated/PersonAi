from __future__ import annotations

from personal_agent.memory.models import CandidateMemoryDraft, MemoryConflict


class MemoryConflictDetector:
    """Conservative v1 conflict detector; it never overwrites memories."""

    MUTUALLY_EXCLUSIVE_TERMS = (
        ("考研", "就业"),
        ("全职", "兼职"),
        ("喜欢", "不喜欢"),
        ("需要", "不需要"),
        ("使用", "停止使用"),
    )

    def detect(
        self,
        candidate: CandidateMemoryDraft,
        active_memories: list[dict[str, object]],
    ) -> list[MemoryConflict]:
        conflicts: list[MemoryConflict] = []
        new_content = candidate.content.casefold()
        for memory in active_memories:
            if str(memory.get("type")) != candidate.type:
                continue
            old_content = str(memory.get("content", ""))
            old_normalized = old_content.casefold()
            if old_normalized == new_content:
                conflicts.append(
                    MemoryConflict(
                        old_memory_id=int(memory["id"]),
                        old_content=old_content,
                        new_content=candidate.content,
                        reason="与现有记忆重复",
                    )
                )
                continue
            for left, right in self.MUTUALLY_EXCLUSIVE_TERMS:
                if (
                    left.casefold() in old_normalized
                    and right.casefold() in new_content
                ) or (
                    right.casefold() in old_normalized
                    and left.casefold() in new_content
                ):
                    conflicts.append(
                        MemoryConflict(
                            old_memory_id=int(memory["id"]),
                            old_content=old_content,
                            new_content=candidate.content,
                            reason=f"检测到可能互斥的表达：{left}/{right}",
                        )
                    )
                    break
        return conflicts
