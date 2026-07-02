from __future__ import annotations

import pandas as pd
import pytest
from pandas.io.formats.style import Styler

from qa_weekly_analytics.viz.table_styles import (
    TableStyleError,
    style_critical_table,
    style_ranking_table,
    style_recurrence_table,
)


def test_style_ranking_table_returns_styler() -> None:
    df = pd.DataFrame(
        [
            {"agent": "Ana", "count": 4, "share": 0.5, "cumulative_share": 0.5},
            {"agent": "Juan", "count": 2, "share": 0.25, "cumulative_share": 0.75},
        ]
    )

    styled = style_ranking_table(df)

    assert isinstance(styled, Styler)
    html = styled.to_html()
    assert "50.0%" in html
    assert "25.0%" in html


def test_style_ranking_table_handles_empty_df() -> None:
    df = pd.DataFrame(columns=["agent", "count", "share"])

    styled = style_ranking_table(df)

    assert isinstance(styled, Styler)


def test_style_ranking_table_rejects_invalid_input() -> None:
    with pytest.raises(TableStyleError):
        style_ranking_table("not-a-dataframe")  # type: ignore[arg-type]


def test_style_critical_table_returns_styler_with_highlight() -> None:
    df = pd.DataFrame(
        [
            {
                "date": "01/06/2026",
                "agent": "Ana",
                "ticket_id": "T1",
                "reason": "Pago",
                "notes": "Crítico",
            }
        ]
    )

    styled = style_critical_table(df)

    assert isinstance(styled, Styler)
    html = styled.to_html()
    assert "background-color" in html


def test_style_recurrence_table_returns_styler() -> None:
    df = pd.DataFrame(
        [
            {"ticket_id": "T1", "count": 3},
            {"ticket_id": "T2", "count": 2},
        ]
    )

    styled = style_recurrence_table(df)

    assert isinstance(styled, Styler)