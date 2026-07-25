"""Backward-compatible conversation facade.

New code should inject ``Agent`` and ``DailyAnalysisService`` directly.
"""

from __future__ import annotations

from datetime import date

from personal_agent.bootstrap import create_application

_application = None


def _default_application():
    global _application
    if _application is None:
        _application = create_application()
        _application.repository.initialize()
    return _application


def chat(user_text: str) -> str:
    return _default_application().agent.chat(user_text)


def analyze_and_purge_chat(analysis_date: date):
    return _default_application().daily_analysis.analyze_and_purge(analysis_date)


def process_pending_daily_analyses(today: date | None = None):
    return _default_application().daily_analysis.process_pending(today)


def get_formatted_daily_analysis(analysis_date: date):
    return _default_application().daily_analysis.formatted_analysis(analysis_date)
