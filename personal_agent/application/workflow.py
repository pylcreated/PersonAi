from __future__ import annotations

import logging
import threading
import traceback
from datetime import date, datetime, timedelta
from typing import Callable, Protocol

import schedule

from personal_agent.analysis import DailyAnalysisService, WeeklyReviewService
from personal_agent.core.clock import local_now
from personal_agent.memory.repository import AgentRepository

logger = logging.getLogger(__name__)
SCHEDULE_TAG = "local_assistant"


class MessageChannel(Protocol):
    def send_message(self, to: str, subject: str, body: str) -> None: ...


class WorkflowScheduler:
    """Owns recurring workflows; CLI only requests reconfiguration."""

    def __init__(
        self,
        repository: AgentRepository,
        daily_analysis: DailyAnalysisService,
        weekly_review: WeeklyReviewService,
        channel: MessageChannel,
        clock: Callable[[], datetime] = local_now,
        backup_database: Callable[[], object] | None = None,
    ) -> None:
        self.repository = repository
        self.daily_analysis = daily_analysis
        self.weekly_review = weekly_review
        self.channel = channel
        self.clock = clock
        self.backup_database = backup_database
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def configure(self, reminder_hour: int) -> None:
        schedule.clear(SCHEDULE_TAG)
        at_time = f"{reminder_hour:02d}:00"
        schedule.every().day.at(at_time).do(
            self.safe_run,
            "daily_reminder",
            self.send_daily_reminder,
        ).tag(SCHEDULE_TAG)
        schedule.every().sunday.at(at_time).do(
            self.safe_run,
            "weekly_review",
            self.send_weekly_review,
        ).tag(SCHEDULE_TAG)
        schedule.every().day.at("00:05").do(
            self.safe_run,
            "daily_analysis",
            self.daily_analysis.process_pending,
        ).tag(SCHEDULE_TAG)
        schedule.every(30).minutes.do(
            self.safe_run,
            "daily_analysis_retry",
            self.daily_analysis.process_pending,
        ).tag(SCHEDULE_TAG)
        if self.backup_database is not None:
            schedule.every().day.at("00:30").do(
                self.safe_run,
                "daily_database_backup",
                self.backup_database,
            ).tag(SCHEDULE_TAG)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        schedule.clear(SCHEDULE_TAG)

    def run_startup_catchup(self) -> None:
        self.safe_run(
            "startup_daily_analysis",
            self.daily_analysis.process_pending,
        )

    def send_daily_reminder(self) -> None:
        goals = self.repository.active_goals()
        goal_text = "\n".join(f"- {goal['title']}" for goal in goals)
        self.channel.send_message(
            "local",
            "每日复盘提醒",
            f"现在可以聊聊今天的进展、阻碍和下一步。\n{goal_text}",
        )

    def send_weekly_review(self) -> None:
        today = self.clock().date()
        week_start = today - timedelta(days=today.weekday())
        self.channel.send_message(
            "local",
            "本周复盘报告",
            self.weekly_review.generate(week_start),
        )

    def safe_run(
        self,
        task_name: str,
        function: Callable[[], object],
    ) -> None:
        try:
            function()
        except Exception as exc:  # pragma: no cover - runtime defense
            stack_trace = traceback.format_exc()
            logger.error("Scheduled task %s failed: %s", task_name, exc)
            self.repository.log_error(
                task_name,
                f"{type(exc).__name__}: {exc}\n{stack_trace}",
            )

    def _run_loop(self) -> None:
        while not self.stop_event.wait(1):
            schedule.run_pending()
