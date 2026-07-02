from __future__ import annotations

import pytest

from qa_weekly_analytics.storage.settings import Settings, SettingsError, _DEFAULT_DATA_URL


def test_settings_load_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIMEZONE", "America/Bogota")

    settings = Settings.from_env()

    assert settings.DATA_URL == _DEFAULT_DATA_URL
    assert settings.TIMEZONE == "America/Bogota"
    assert settings.SCHEDULER_ENABLED is False


def test_settings_load_with_custom_data_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_URL", "https://example.com/data.csv")
    monkeypatch.setenv("TIMEZONE", "America/Bogota")

    settings = Settings.from_env()

    assert settings.DATA_URL == "https://example.com/data.csv"
    assert settings.TIMEZONE == "America/Bogota"


def test_settings_defaults() -> None:
    """Verifica que Settings() con defaults funcione sin .env ni env vars."""
    settings = Settings()

    assert settings.DATA_URL == _DEFAULT_DATA_URL
    assert settings.TIMEZONE == "America/Bogota"
    assert settings.SCHEDULER_ENABLED is False


def test_invalid_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIMEZONE", "Bogota")

    with pytest.raises(SettingsError):
        Settings.from_env()
