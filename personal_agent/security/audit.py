from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class AuditEvent:
    timestamp: datetime
    actor: str
    tool: str
    action: str
    target: str
    allowed: bool
    result: str
    approval: str = "none"
    detail: str = ""


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...


class NullAuditSink:
    """No-op adapter for isolated callers that explicitly do not persist logs."""

    def record(self, event: AuditEvent) -> None:
        return None


class JsonlAuditSink:
    """Append-only local audit log with one JSON object per operation."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def record(self, event: AuditEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "time": event.timestamp.isoformat(),
            "actor": event.actor,
            "tool": event.tool,
            "action": event.action,
            "target": event.target,
            "allowed": event.allowed,
            "result": event.result,
            "approval": event.approval,
            "detail": event.detail,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def recent(self, limit: int = 50) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        results: list[dict[str, object]] = []
        for line in lines[-max(0, limit) :]:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                results.append(value)
        return results
