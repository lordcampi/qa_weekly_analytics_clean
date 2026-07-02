from __future__ import annotations

from datetime import date

import pandas as pd

from qa_weekly_analytics.domain.date_ranges import DateRange
from qa_weekly_analytics.kpis.wow_recurrence import analyze_wow_recurrence
from qa_weekly_analytics.storage.historic_schema import HISTORIC_TABS, RESUMEN_SCHEMA, SCHEMA_BY_TAB
from qa_weekly_analytics.storage.weekly_snapshot import build_weekly_snapshot
from qa_weekly_analytics.kpis.weekly_summary import compute_kpis


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_number": [2, 3, 4, 5, 6],
            "date": [date(2026, 6, 1), date(2026, 6, 1), date(2026, 5, 26), date(2026, 5, 26), date(2026, 5, 27)],
            "agent": ["Ana", "Ana", "Ana", "Juan", "Juan"],
            "ticket_id": ["T1", "T1", "T2", "T3", "T3"],
            "reason": ["Pago", "Pago", "Login", "Login", "Login"],
            "is_critical": [True, False, False, True, False],
            "notes": ["", "", "", "", ""],
        }
    )


def test_historic_schema_tabs() -> None:
    assert len(HISTORIC_TABS) == 4
    assert "week_id" in RESUMEN_SCHEMA.columns
    assert SCHEMA_BY_TAB["Hist_Resumen_Semanal"].tab_name == "Hist_Resumen_Semanal"


def test_build_weekly_snapshot_columns() -> None:
    df = _sample_df()
    week = DateRange(date(2026, 6, 1), date(2026, 6, 5))
    kpis = compute_kpis(df, start_date=week.start_date, end_date=week.end_date)
    prev = DateRange(date(2026, 5, 25), date(2026, 5, 29))
    wow = analyze_wow_recurrence(df, current_week=week, previous_week=prev)
    snap = build_weekly_snapshot(week_range=week, kpis=kpis, wow=wow, previous_week_id="2026-05-25_2026-05-29")

    assert snap.week_id == "2026-06-01_2026-06-05"
    assert list(snap.resumen.columns) == list(RESUMEN_SCHEMA.columns)
    assert int(snap.resumen.iloc[0]["total_errors"]) == 2
    assert not snap.por_agente.empty
    assert snap.por_agente.iloc[0]["agent"] == "Ana"
