from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from qa_weekly_analytics.app.dashboard_logic import quincena_preset_labels, resolve_selected_weeks, week_options_for_ui
from qa_weekly_analytics.domain.date_ranges import DateRange
from qa_weekly_analytics.reporting.excel_export import append_snapshot_to_excel
from qa_weekly_analytics.storage.weekly_snapshot import build_weekly_snapshot
from qa_weekly_analytics.kpis.weekly_summary import compute_kpis
from qa_weekly_analytics.kpis.wow_recurrence import analyze_wow_recurrence


def test_week_options_and_quincena_preset() -> None:
    weeks = [
        DateRange(date(2026, 6, 8), date(2026, 6, 12)),
        DateRange(date(2026, 6, 1), date(2026, 6, 5)),
    ]
    opts = week_options_for_ui(weeks)
    preset = quincena_preset_labels(opts, 2)
    assert len(preset) == 2
    resolved = resolve_selected_weeks(preset, opts)
    assert len(resolved) == 2


def test_append_snapshot_to_excel_idempotent(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "row_number": [2],
            "date": [date(2026, 6, 1)],
            "agent": ["Ana"],
            "ticket_id": ["T1"],
            "reason": ["Pago"],
            "is_critical": [False],
            "notes": [""],
        }
    )
    week = DateRange(date(2026, 6, 1), date(2026, 6, 5))
    kpis = compute_kpis(df, start_date=week.start_date, end_date=week.end_date)
    prev = DateRange(date(2026, 5, 25), date(2026, 5, 29))
    wow = analyze_wow_recurrence(df, current_week=week, previous_week=prev)
    snap = build_weekly_snapshot(week_range=week, kpis=kpis, wow=wow)

    excel_path = tmp_path / "hist.xlsx"
    append_snapshot_to_excel(snap, excel_path)
    assert excel_path.exists()

    with pytest.raises(Exception):
        append_snapshot_to_excel(snap, excel_path, skip_if_exists=True)
