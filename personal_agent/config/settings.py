from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=PROJECT_DIR / ".env", override=False)

CONFIG_FILE = PROJECT_DIR / ".bot_config.json"


@dataclass(frozen=True)
class AppConfig:
    """Configuration for the local assistant and its LLM provider."""

    openai_api_key: str
    openai_api_base: str
    llm_provider: str
    llm_api_key: str
    llm_api_url: str
    llm_model_name: str
    ollama_base_url: str
    default_ask_hour: int
    openai_mock_mode: bool


def _get_int(value: object, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if 0 <= result <= 23 else default


def _load_runtime_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_runtime_config(default_ask_hour: int) -> None:
    """Persist the reminder hour selected inside the application."""
    if not 0 <= default_ask_hour <= 23:
        raise ValueError("default_ask_hour must be between 0 and 23")
    runtime_config = _load_runtime_config()
    runtime_config["default_ask_hour"] = default_ask_hour
    CONFIG_FILE.write_text(
        json.dumps(runtime_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_model_runtime_config(model_name: str) -> None:
    """Persist the selected model name; it takes effect after restart."""
    cleaned = (model_name or "").strip()
    if not cleaned or len(cleaned) > 120:
        raise ValueError("model_name must contain 1-120 characters")
    runtime_config = _load_runtime_config()
    runtime_config["llm_model_name"] = cleaned
    CONFIG_FILE.write_text(
        json.dumps(runtime_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_config() -> AppConfig:
    """Return configuration, preferring an in-app reminder setting over .env."""
    runtime_config = _load_runtime_config()
    env_default = _get_int(os.getenv("DEFAULT_ASK_HOUR"), 20)
    default_ask_hour = _get_int(
        runtime_config.get("default_ask_hour"),
        env_default,
    )

    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_api_base=os.getenv("OPENAI_API_BASE", ""),
        llm_provider=os.getenv("LLM_PROVIDER", "openai"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_api_url=os.getenv("LLM_API_URL", ""),
        llm_model_name=str(
            runtime_config.get("llm_model_name")
            or os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
        ),
        ollama_base_url=os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ).rstrip("/"),
        default_ask_hour=default_ask_hour,
        openai_mock_mode=os.getenv("OPENAI_MOCK_MODE", "true").lower() == "true",
    )
