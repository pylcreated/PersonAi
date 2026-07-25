from __future__ import annotations

from datetime import datetime, timedelta, timezone

LOCAL_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


def local_now() -> datetime:
    """Return the current timezone-aware application time."""
    return datetime.now(LOCAL_TIMEZONE)
