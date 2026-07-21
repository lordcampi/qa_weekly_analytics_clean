from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import plotly.graph_objects as go

from qa_weekly_analytics.viz.dashboard_charts import (
    GOAL_ERRORS_PER_WEEK,
    agents_comparison_trend_line,
    classify_agents_vs_average,
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
    title_text = getattr(fig.layout.title, "text", fig.layout.title)
    assert title_text in (None, "")
    assert title_text != "undefined"
    assert fig.layout.hovermode == "x unified"
    assert any(
        getattr(shape, "y0", None) == GOAL_ERRORS_PER_WEEK
        or (isinstance(shape, dict) and shape.get("y0") == GOAL_ERRORS_PER_WEEK)
        for shape in (fig.layout.shapes or [])
    )


def test_agents_comparison_trend_line_empty_returns_figure() -> None:
    fig = agents_comparison_trend_line([], {})

    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0


def test_classify_agents_vs_average_splits_above_and_below() -> None:
    series = {
        "Ana": [4, 4, 4],  # avg 4
        "Juan": [2, 2, 2],  # avg 2
        "Pedro": [1, 1, 1],  # avg 1
    }
    # team avg = (4+2+1)/3 = 2.33

    result = classify_agents_vs_average(series)

    assert list(result.columns) == ["agent", "avg_weekly", "team_avg", "diff", "status"]
    by_agent = result.set_index("agent")
    assert by_agent.loc["Ana", "status"] == "Por encima"
    assert by_agent.loc["Pedro", "status"] == "Por debajo"
    assert by_agent.loc["Juan", "status"] == "Por debajo"
    assert float(by_agent.loc["Ana", "team_avg"]) == float(by_agent.loc["Pedro", "team_avg"])


def test_classify_agents_vs_average_empty() -> None:
    result = classify_agents_vs_average({})

    assert result.empty
    assert list(result.columns) == ["agent", "avg_weekly", "team_avg", "diff", "status"]
