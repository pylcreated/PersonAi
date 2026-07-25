from __future__ import annotations

from typing import Any

import requests


class GenericHTTPClient:
    """Adapter for simple prompt-based HTTP model endpoints."""

    def __init__(
        self,
        model_name: str,
        api_url: str,
        api_key: str = "",
    ) -> None:
        self._model_name = model_name
        self.api_url = api_url
        self.api_key = api_key

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        if not self.api_url:
            raise RuntimeError("未配置 LLM_API_URL")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": 0.3,
            "max_tokens": 800,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("模型接口返回格式无效")
        for key in ("text", "output_text", "content", "response"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    return message["content"].strip()
                if isinstance(first.get("text"), str):
                    return first["text"].strip()
        raise RuntimeError("无法解析模型接口返回内容")
