from __future__ import annotations

from datetime import date, datetime

import pytest

from qa_weekly_analytics.domain.normalization import normalize_dates, parse_mixed_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("04/06/2026", date(2026, 6, 4)),
        ("4/6/2026", date(2026, 6, 4)),
        ("  04/06/2026  ", date(2026, 6, 4)),
        ("4 de junio 2026", date(2026, 6, 4)),
        ("4 de Junio 2026", date(2026, 6, 4)),
        (" 4   de   junio   2026 ", date(2026, 6, 4)),
        (date(2026, 6, 4), date(2026, 6, 4)),
        (datetime(2026, 6, 4, 10, 30), date(2026, 6, 4)),
    ],
)
def test_parse_mixed_date_valid(raw, expected) -> None:
    assert parse_mixed_date(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",  # vacío
        "   ",  # espacios
        None,
        "32/01/2026",  # día inválido
        "31/02/2026",  # fecha inválida
        "2026/06/04",  # formato no soportado
        "4 junio 2026",  # falta "de"
        "4 de junio",  # falta año
        "4 de foo 2026",  # mes no reconocido
    ],
)
def test_parse_mixed_date_invalid(raw) -> None:
    assert parse_mixed_date(raw) is None


def test_normalize_dates_reports_invalid_and_empty() -> None:
    values = [
        "04/06/2026",       # ok
        "4 de junio 2026",  # ok
        "",                 # empty
        "31/02/2026",       # invalid
        None,               # empty
        "4 de foo 2026",    # invalid
    ]
    report = normalize_dates(values)

    assert report.parsed[0] == date(2026, 6, 4)
    assert report.parsed[1] == date(2026, 6, 4)
    assert report.parsed[2] is None
    assert report.parsed[3] is None
    assert report.parsed[4] is None
    assert report.parsed[5] is None

    assert report.empty_indices == [2, 4]
    assert report.invalid_indices == [3, 5]