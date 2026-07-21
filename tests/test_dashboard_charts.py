from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from qa_weekly_analytics.viz.dashboard_charts import (
    GOAL_ERRORS_PER_WEEK,
    agents_comparison_trend_line,
    critical_vs_non_critical_stacked,
    pareto_agents_chart,
    top_agents_bar,
    top_reasons_bar,
    trend_lv_bar,
)


@dataclass(frozen=True)
class _DummyKpis:
    trend_daily: pd.DataFrame
    by_agent: pd.DataFrame
    by_reason: pd.DataFrame


def _kpis_fixture() -> _DummyKpis:
    return _DummyKpis(
        trend_daily=pd.DataFrame(
            [
                {"date": date(2026, 6, 1), "count": 2},
                {"date": date(2026, 6, 2), "count": 3},
            ]
        ),
        by_agent=pd.DataFrame(
            [
                {"agent": "Ana", "count": 4, "share": 0.5, "cumulative_share": 0.5},
                {"agent": "Juan", "count": 2, "share": 0.25, "cumulative_share": 0.75},
                {"agent": "Pedro", "count": 2, "share": 0.25, "cumulative_share": 1.0},
            ]
        ),
        by_reason=pd.DataFrame(
            [
                {"reason": "Pago", "count": 5, "share": 0.625, "cumulative_share": 0.625},
                {"reason": "Login", "count": 3, "share": 0.375, "cumulative_share": 1.0},
            ]
        ),
    )


def test_trend_lv_bar_returns_figure() -> None:
    fig = trend_lv_bar(_kpis_fixture())

    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_top_agents_bar_returns_figure() -> None:
    fig = top_agents_bar(_kpis_fixture(), top_n=2)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_top_reasons_bar_returns_figure() -> None:
    fig = top_reasons_bar(_kpis_fixture(), top_n=2)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_pareto_agents_chart_returns_bar_and_line() -> None:
    fig = pareto_agents_chart(_kpis_fixture(), top_n=3)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_critical_vs_non_critical_stacked_returns_figure() -> None:
    df = pd.DataFrame(
        [
            {"date": date(2026, 6, 1), "agent": "Ana", "reason": "Pago", "is_critical": True},
            {"date": date(2026, 6, 1), "agent": "Ana", "reason": "Login", "is_critical": False},
            {"date": date(2026, 6, 2), "agent": "Juan", "reason": "Pago", "is_critical": None},
        ]
    )

    fig = critical_vs_non_critical_stacked(
        df,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 5),
    )

    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 1


def test_agents_comparison_trend_line_has_one_trace_per_agent() -> None:
    week_labels = ["2026-W22", "2026-W23", "2026-W24"]
    series = {
        "Ana": [3, 1, 4],
        "Juan": [1, 2, 0],
        "Pedro": [0, 1, 2],
    }

    fig = agents_comparison_trend_line(week_labels, series)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3
    assert {trace.name for trace in fig.data} == {"Ana", "Juan", "Pedro"}
    assert any(
        getattr(shape, "y0", None) == GOAL_ERRORS_PER_WEEK
        or (isinstance(shape, dict) and shape.get("y0") == GOAL_ERRORS_PER_WEEK)
        for shape in (fig.layout.shapes or [])
    )


def test_agents_comparison_trend_line_empty_returns_figure() -> None:
    fig = agents_comparison_trend_line([], {})

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
