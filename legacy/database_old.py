"""Backward-compatible database imports.

New code should depend on ``AgentRepository`` rather than this module.
"""

from personal_agent.memory.database import *  # noqa: F401,F403
