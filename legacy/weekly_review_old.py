"""Backward-compatible weekly review facade."""

from __future__ import annotations

from datetime import date

from personal_agent.bootstrap import create_application


def generate_weekly_review(week_start: str) -> str:
    application = create_application()
    application.repository.initialize()
    return application.weekly_review.generate(date.fromisoformat(week_start))
