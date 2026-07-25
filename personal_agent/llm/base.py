from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """Provider-neutral text generation interface used by the agent."""

    @property
    def model_name(self) -> str:
        ...

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        ...
