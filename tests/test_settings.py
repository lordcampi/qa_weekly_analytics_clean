from __future__ import annotations

import pytest

from qa_weekly_analytics.storage.settings import Settings, SettingsError


def test_settings_load_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHEET_ID", "sheet12345")
    monkeypatch.setenv("TIMEZONE", "America/Bogota")

    settings = Settings.from_env()

    assert settings.SHEET_ID == "sheet12345"
    assert settings.TIMEZONE == "America/Bogota"
    assert settings.SHEET_TAB == "Operativa 2026"
    assert settings.HIST_TAB_RESUMEN == "Hist_Resumen_Semanal"
    assert settings.SCHEDULER_ENABLED is False


def test_invalid_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHEET_ID", "sheet12345")
    monkeypatch.setenv("TIMEZONE", "Bogota")

    with pytest.raises(SettingsError):
        Settings.from_env()
