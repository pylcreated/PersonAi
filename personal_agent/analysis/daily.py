from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any, Callable

from personal_agent.core.clock import local_now
from personal_agent.memory.analyzer import DailyMemoryAnalyzer
from personal_agent.memory.repository import AgentRepository

logger = logging.getLogger(__name__)


class DailyAnalysisService:
    """Analyzes expired chats and purges raw messages after a safe commit."""

    def __init__(
        self,
        repository: AgentRepository,
        analyzer: DailyMemoryAnalyzer,
        clock: Callable[[], datetime] = local_now,
        backup_after_success: Callable[[], object] | None = None,
    ) -> None:
        self.repository = repository
        self.analyzer = analyzer
        self.clock = clock
        self.backup_after_success = backup_after_success

    def analyze_and_purge(self, analysis_date: date) -> dict[str, Any] | None:
        messages = self.repository.messages_for_date(analysis_date)
        if not messages:
            return None

        try:
            result = self.analyzer.analyze(analysis_date, messages)

            self.repository.save_analysis_and_purge(
                analysis_date=analysis_date,
                analysis=result.analysis,
                model_name=self.analyzer.model_name,
                message_count=len(messages),
                created_at=self.clock().isoformat(),
                memory_candidates=[
                    candidate.as_dict() for candidate in result.candidates
                ],
                evidence=[item.as_dict() for item in result.evidence],
            )
            if self.backup_after_success is not None:
                try:
                    self.backup_after_success()
                except Exception as exc:
                    logger.exception("日报成功后的数据库备份失败")
                    try:
                        self.repository.log_error(
                            "database_backup",
                            f"{type(exc).__name__}: {exc}",
                        )
                    except Exception:
                        logger.exception("数据库备份失败日志写入失败")
            return result.analysis
        except Exception as exc:
            self.repository.mark_session_failed(
                analysis_date,
                f"{type(exc).__name__}: {exc}",
            )
            raise

    def process_pending(self, today: date | None = None) -> list[date]:
        local_today = today or self.clock().date()
        completed: list[date] = []
        for pending_date in self.repository.pending_chat_dates(local_today):
            if self.analyze_and_purge(pending_date) is not None:
                completed.append(pending_date)
        return completed

    def formatted_analysis(self, analysis_date: date) -> str | None:
        analysis = self.repository.daily_analysis(analysis_date)
        return self.format_analysis(analysis) if analysis else None

    @staticmethod
    def format_analysis(analysis: dict[str, object]) -> str:
        def render_list(value: object) -> str:
            items = value if isinstance(value, list) else []
            return "\n".join(f"- {item}" for item in items) or "- 无"

        evidence = analysis.get("evidence")
        evidence_text = ""
        if isinstance(evidence, list) and evidence:
            rendered = "\n".join(
                f"- [{item.get('evidence_type')}] {item.get('claim')}\n"
                f"  来源：消息 #{item.get('message_id')} "
                f"{item.get('message_created_at')}\n"
                f"  原文：{item.get('quote')}"
                for item in evidence
                if isinstance(item, dict)
            )
            evidence_text = f"\n\n证据：\n{rendered}"

        return (
            f"日期：{analysis['analysis_date']}\n\n"
            f"总结：\n{analysis['summary']}\n\n"
            f"进展：\n{render_list(analysis['progress'])}\n\n"
            f"模式：\n{render_list(analysis['patterns'])}\n\n"
            f"状态：\n{analysis['mood']}\n\n"
            f"下一步：\n{render_list(analysis['next_actions'])}"
            f"\n\n可信度：{float(analysis.get('confidence', 0.5)):.2f}"
            f"{evidence_text}"
        )
