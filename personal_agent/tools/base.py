from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    success: bool
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolAuthorization:
    action: str
    target: str
    requires_confirmation: bool = False


class Tool(Protocol):
    """Tool capability. Implementations never decide whether they may execute."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def required_permission(self) -> str: ...

    @property
    def input_schema(self) -> Mapping[str, object]: ...

    def authorizations(
        self,
        arguments: dict[str, Any],
    ) -> list[ToolAuthorization]: ...

    def execute(self, arguments: dict[str, Any]) -> ToolResult: ...
