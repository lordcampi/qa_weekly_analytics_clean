from __future__ import annotations

import pytest

from qa_weekly_analytics.jobs.scheduler import start_scheduler, stop_scheduler
from qa_weekly_analytics.storage.settings import Settings


def test_scheduler_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHEET_ID", "sheet12345")
    settings = Settings.from_env()
    assert settings.SCHEDULER_ENABLED is False
    assert start_scheduler(settings) is None
    stop_scheduler()
