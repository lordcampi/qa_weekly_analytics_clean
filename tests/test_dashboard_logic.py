from __future__ import annotations

from datetime import datetime, date, timezone

import pandas as pd

from qa_weekly_analytics.app.dashboard_logic import compute_default_range, get_filter_options, map_critical_choice


def test_map_critical_choice() -> None:
    assert map_critical_choice("Todos") is None
    assert map_critical_choice("Sólo críticos") is True
    assert map_critical_choice("Sólo no críticos") is False
    assert map_critical_choice("   ") is None


def test_get_filter_options() -> None:
    df = pd.DataFrame(
        {
            "agent": ["Ana", "Juan", "Ana", "", None],
            "reason": ["Pago", "Login", "Pago", "Search", None],
        }
    )
    opts = get_filter_options(df)
    assert opts.agents == ["Ana", "Juan"]
    assert opts.reasons == ["Login", "Pago", "Search"]


def test_compute_default_range_is_previous_week_lv() -> None:
    # Lunes 2026-06-08 -> semana anterior: 2026-06-01 a 2026-06-05
    start_d, end_d = compute_default_range("America/Bogota", now=datetime(2026, 6, 8, 9, 0))
    assert start_d == date(2026, 6, 1)
    assert end_d == date(2026, 6, 5)

    # Domingo en Bogota via UTC (2026-06-07 21:00 Bogota)
    now_utc = datetime(2026, 6, 8, 2, 0, tzinfo=timezone.utc)
    start_d, end_d = compute_default_range("America/Bogota", now=now_utc)
    assert start_d == date(2026, 5, 25)
    assert end_d == date(2026, 5, 29)