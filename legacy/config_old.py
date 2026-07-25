"""Backward-compatible configuration imports.

New code should import from ``personal_agent.config``.
"""

from personal_agent.config.settings import (
    AppConfig,
    CONFIG_FILE,
    PROJECT_DIR,
    get_config,
    save_runtime_config,
)

__all__ = [
    "AppConfig",
    "CONFIG_FILE",
    "PROJECT_DIR",
    "get_config",
    "save_runtime_config",
]
