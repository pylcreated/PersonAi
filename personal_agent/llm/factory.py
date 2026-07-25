from __future__ import annotations

from personal_agent.config import AppConfig
from personal_agent.llm.base import LLMClient
from personal_agent.llm.generic_http import GenericHTTPClient
from personal_agent.llm.mock import MockLLMClient
from personal_agent.llm.ollama import OllamaClient
from personal_agent.llm.openai_compatible import OpenAICompatibleClient


def create_llm_client(config: AppConfig) -> LLMClient:
    """Build the configured provider without leaking provider details into core."""
    if config.openai_mock_mode:
        return MockLLMClient()

    provider = config.llm_provider.lower()
    if provider == "ollama":
        return OllamaClient(
            model_name=config.llm_model_name,
            base_url=config.ollama_base_url,
        )
    if provider in {"openai", "deepseek"}:
        api_key = config.llm_api_key or config.openai_api_key
        if not api_key:
            raise RuntimeError("未配置模型 API Key")
        return OpenAICompatibleClient(
            model_name=config.llm_model_name,
            api_key=api_key,
            base_url=config.llm_api_url or config.openai_api_base,
        )
    return GenericHTTPClient(
        model_name=config.llm_model_name,
        api_url=config.llm_api_url,
        api_key=config.llm_api_key,
    )
