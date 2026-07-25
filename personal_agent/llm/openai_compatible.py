from __future__ import annotations

from openai import OpenAI


class OpenAICompatibleClient:
    """OpenAI-compatible client for OpenAI, DeepSeek, or similar providers."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        base_url: str = "",
    ) -> None:
        self._model_name = model_name
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/") or None,
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(self, prompt: str, *, json_mode: bool = False) -> str:
        kwargs: dict[str, object] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个简洁、可靠、只依据给定信息回答的中文助手。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
            **kwargs,
        )
        if not response.choices:
            raise RuntimeError("模型没有返回候选结果")
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("模型没有返回有效内容")
        return content.strip()
