from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from qa_weekly_analytics.domain.date_ranges import (
    DateRange,
    list_monday_friday_weeks,
    merge_week_ranges,
    monday_friday_for_date,
    week_id_from_range,
    week_label,
)
from qa_weekly_analytics.domain.period_comparison import comparison_ranges_for_period, period_length_days


def test_week_id_from_range() -> None:
    assert week_id_from_range(date(2026, 6, 1), date(2026, 6, 5)) == "2026-06-01_2026-06-05"


def test_monday_friday_for_date() -> None:
    rng = monday_friday_for_date(date(2026, 6, 3))  # miércoles
    assert rng.start_date == date(2026, 6, 1)
    assert rng.end_date == date(2026, 6, 5)


def test_list_monday_friday_weeks() -> None:
    df = pd.DataFrame({"date": [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 8)]})
    weeks = list_monday_friday_weeks(df, min_rows=1)
    assert len(weeks) == 2
    assert weeks[0].start_date == date(2026, 6, 8)


def test_merge_week_ranges() -> None:
    w1 = DateRange(date(2026, 6, 1), date(2026, 6, 5))
    w2 = DateRange(date(2026, 6, 8), date(2026, 6, 12))
    merged = merge_week_ranges([w1, w2])
    assert merged.start_date == date(2026, 6, 1)
    assert merged.end_date == date(2026, 6, 12)


def test_week_label() -> None:
    lbl = week_label(DateRange(date(2026, 6, 1), date(2026, 6, 5)))
    assert "01/06/2026" in lbl
    assert "L-V" in lbl


def test_period_length_days() -> None:
    assert period_length_days(date(2026, 6, 1), date(2026, 6, 5)) == 5
    assert period_length_days(date(2026, 6, 1), date(2026, 6, 14)) == 14


def test_comparison_ranges_symmetric_week() -> None:
    current, previous = comparison_ranges_for_period(date(2026, 6, 8), date(2026, 6, 12))
    assert current.start_date == date(2026, 6, 8)
    assert previous.end_date == date(2026, 6, 7)
    assert period_length_days(previous.start_date, previous.end_date) == 5


def test_comparison_ranges_quincena() -> None:
    current, previous = comparison_ranges_for_period(date(2026, 6, 1), date(2026, 6, 14))
    assert period_length_days(current.start_date, current.end_date) == 14
    assert period_length_days(previous.start_date, previous.end_date) == 14


def test_invalid_period_raises() -> None:
    with pytest.raises(ValueError):
        period_length_days(date(2026, 6, 10), date(2026, 6, 1))
