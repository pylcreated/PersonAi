from __future__ import annotations

from typing import Any

import requests


class OllamaClient:
    """Local Ollama implementation of the LLM client interface."""

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 180,
    ) -> None:
        self._model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个简洁、可靠、只依据给定信息回答的中文助手。",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.3,
                "num_ctx": 4096,
                "num_predict": 600 if json_mode else 300,
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise RuntimeError(
                f"无法连接本地 Ollama 服务 {self.base_url}：{exc}"
            ) from exc
        except ValueError as exc:
            raise RuntimeError("Ollama 返回了无效 JSON") from exc

        message = data.get("message") if isinstance(data, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama 没有返回有效内容")
        return content.strip()
