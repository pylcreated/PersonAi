from __future__ import annotations

import json


class MockLLMClient:
    """Deterministic offline client used by tests and local demos."""

    @property
    def model_name(self) -> str:
        return "mock"

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        if json_mode:
            return json.dumps(
                {
                    "summary": "信息不足，无法进一步判断",
                    "progress": [],
                    "obstacles": [],
                    "patterns": [],
                    "mood": "信息不足，无法进一步判断",
                    "next_actions": [],
                },
                ensure_ascii=False,
            )
        return "我已经记录。你希望我帮你梳理原因、拆解下一步，还是继续听你说？"
