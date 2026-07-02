from __future__ import annotations

import pytest

from qa_weekly_analytics.domain.normalization import (
    normalize_critical_flags,
    parse_critical_flag,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SI", True),
        ("si", True),
        (" Sí ", True),
        ("s", True),
        ("YES", True),
        ("true", True),
        ("1", True),
        (True, True),
        ("NO", False),
        (" no ", False),
        ("n", False),
        ("false", False),
        ("0", False),
        (False, False),
    ],
)
def test_parse_critical_flag_valid(raw, expected) -> None:
    assert parse_critical_flag(raw) is expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "maybe",
        "ok",
        "2",
        "siempre",
    ],
)
def test_parse_critical_flag_invalid_or_empty(raw) -> None:
    assert parse_critical_flag(raw) is None


def test_normalize_critical_flags_reports_invalid_and_empty() -> None:
    values = [
        "SI",      # ok True
        "NO",      # ok False
        "",        # empty
        None,      # empty
        "maybe",   # invalid
        "  ok  ",  # invalid
    ]
    report = normalize_critical_flags(values)

    assert report.parsed == [True, False, None, None, None, None]
    assert report.empty_indices == [2, 3]
    assert report.invalid_indices == [4, 5]