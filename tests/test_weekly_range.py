from __future__ import annotations

from datetime import datetime, date, timezone

import pytest

from qa_weekly_analytics.domain.date_ranges import DateRangeError, previous_week_monday_friday


@pytest.mark.parametrize(
    ("now", "expected_start", "expected_end"),
    [
        # Lunes (en Bogota) -> semana anterior L-V
        (datetime(2026, 6, 8, 9, 0), date(2026, 6, 1), date(2026, 6, 5)),
        # Miércoles -> misma semana anterior
        (datetime(2026, 6, 10, 12, 0), date(2026, 6, 1), date(2026, 6, 5)),
        # Domingo -> semana anterior relativa a la semana "actual" del domingo (semana que contiene el domingo)
        (datetime(2026, 6, 7, 18, 0), date(2026, 5, 25), date(2026, 5, 29)),
        # Sábado -> semana anterior relativa a esa semana
        (datetime(2026, 6, 6, 8, 0), date(2026, 5, 25), date(2026, 5, 29)),
    ],
)
def test_previous_week_monday_friday_naive(now, expected_start, expected_end) -> None:
    rng = previous_week_monday_friday(tz_name="America/Bogota", now=now)
    assert rng.start_date == expected_start
    assert rng.end_date == expected_end


def test_previous_week_monday_friday_aware_utc_converts_to_bogota() -> None:
    # 2026-06-08 02:00 UTC = 2026-06-07 21:00 Bogota (domingo)
    now_utc = datetime(2026, 6, 8, 2, 0, tzinfo=timezone.utc)

    rng = previous_week_monday_friday(tz_name="America/Bogota", now=now_utc)
    assert rng.start_date == date(2026, 5, 25)
    assert rng.end_date == date(2026, 5, 29)


def test_invalid_timezone_raises() -> None:
    with pytest.raises(DateRangeError):
        previous_week_monday_friday(tz_name="Mars/Phobos", now=datetime(2026, 6, 8, 9, 0))
