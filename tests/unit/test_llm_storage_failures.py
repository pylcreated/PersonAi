from __future__ import annotations

import requests
import pytest

from personal_agent.llm.ollama import OllamaClient


@pytest.mark.unit
def test_ollama_unavailable_becomes_clear_runtime_error(monkeypatch) -> None:
    def unavailable(*args, **kwargs):
        del args, kwargs
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "post", unavailable)
    client = OllamaClient(
        "test-model",
        base_url="http://127.0.0.1:1",
        timeout_seconds=1,
    )

    with pytest.raises(RuntimeError, match="无法连接本地 Ollama"):
        client.complete("hello")


@pytest.mark.unit
def test_ollama_invalid_response_json_is_rejected(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: Response())

    with pytest.raises(RuntimeError, match="Ollama 返回了无效 JSON"):
        OllamaClient("test-model").complete("hello")
